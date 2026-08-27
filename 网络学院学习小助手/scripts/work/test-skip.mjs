// 单测：验证 SIA 课时解析 + 完成判定（使用真实页面文本）
import { parseLessonStates, isLessonComplete, toSeconds } from '../worker.js';

let passed = 0;
let failed = 0;
function assert(name, actual, expected) {
  const ok = JSON.stringify(actual) === JSON.stringify(expected);
  if (ok) {
    passed += 1;
    console.log(`[PASS] ${name}`);
  } else {
    failed += 1;
    console.log(`[FAIL] ${name}`);
    console.log(`  实际: ${JSON.stringify(actual)}`);
    console.log(`  期望: ${JSON.stringify(expected)}`);
  }
}

// 1. 真实文本：单课时未完成（已学 6 分钟 / 通过 33 分钟）
const t1 = '2026年县片区经理讲安全（第七期） 完成进度：50% 学习状态： 未通过 学习 第1章:加能站电气安全管理 第1课时:加能站电气安全管理 18% 已学：6分钟 通过：33分钟 状态:未通过 收起';
const g1 = parseLessonStates(t1);
assert('单课时解析', g1.length, 1);
assert('已学时长换算', g1[0] && g1[0].learnedSec, 360);
assert('视频时长换算', g1[0] && g1[0].requiredSec, 1980);
assert('状态解析', g1[0] && g1[0].status, '未通过');
assert('未完成判定', isLessonComplete(g1[0]), false);

// 2. 已学满：已学 33 分钟 == 通过 33 分钟 → 已完成
const t2 = '第1课时:加能站电气安全管理 100% 已学：33分钟 通过：33分钟 状态:未通过';
const g2 = parseLessonStates(t2);
assert('学满解析', g2.length, 1);
assert('学满判定(时长相等)', isLessonComplete(g2[0]), true);

// 3. 状态已通过 → 已完成
const t3 = '第1课时:xxx 100% 已学：33分钟 通过：33分钟 状态:已通过';
const g3 = parseLessonStates(t3);
assert('已通过状态判定', isLessonComplete(g3[0]), true);

// 4. 多课时：全部通过 → 全部完成
const t4 = '第1课时:甲 100% 已学：10分钟 通过：10分钟 状态:已通过 第2课时:乙 100% 已学：20分钟 通过：20分钟 状态:已通过 第3课时:丙 100% 已学：5分钟 通过：5分钟 状态:已通过';
const g4 = parseLessonStates(t4);
assert('多课时解析数量', g4.length, 3);
assert('多课时全部完成', g4.every((g) => isLessonComplete(g)), true);

// 5. 多课时：部分完成 → 不应判为全部完成
const t5 = '第1课时:甲 100% 已学：10分钟 通过：10分钟 状态:已通过 第2课时:乙 50% 已学：10分钟 通过：20分钟 状态:未通过';
const g5 = parseLessonStates(t5);
assert('多课时部分完成解析', g5.length, 2);
assert('部分完成判定', g5.every((g) => isLessonComplete(g)), false);

// 6. 单位混合：已学 0.5 小时 vs 通过 30 分钟
const g6 = parseLessonStates('已学：0.5小时 通过：30分钟 状态:未通过');
assert('单位混合换算', g6[0] && g6[0].learnedSec, 1800);
assert('单位混合完成', isLessonComplete(g6[0]), true);

// 7. 无课时数据
assert('无数据返回空', parseLessonStates('学习评论资料 全部(0) 笔记(0)'), []);

// 8. 超过：已学 40 分钟 > 通过 33 分钟
const g8 = parseLessonStates('已学：40分钟 通过：33分钟 状态:未通过');
assert('超时判定', isLessonComplete(g8[0]), true);

console.log(`\n结果: ${passed} 通过, ${failed} 失败`);
process.exit(failed ? 1 : 0);
