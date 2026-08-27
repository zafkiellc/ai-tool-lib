# -*- coding: utf-8 -*-
"""登录 FSS：填明文 → 点击登录按钮（触发页面自身加密与校验）

用法：
  python login_fss.py                    # 交互式输入用户名密码
  python login_fss.py <user> <password>  # 命令行参数（注意 shell 历史残留风险）
  或设置环境变量 FSS_USER / FSS_PASS 后运行

安全：凭据仅本次进程使用，不写入任何文件。会话状态存到 --state 指定路径（默认 D:/workbuddy/报销/fss_state.json）。
"""
import sys, io, json, os, getpass
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from playwright.sync_api import sync_playwright

def get_credentials():
    """从 环境变量 > 命令行参数 > 交互输入 获取凭据"""
    user = os.environ.get('FSS_USER', '')
    pw = os.environ.get('FSS_PASS', '')
    if not user and len(sys.argv) >= 3:
        user, pw = sys.argv[1], sys.argv[2]
    if not user:
        user = input("FSS 用户名 (如 lvch36): ").strip()
    if not pw:
        pw = getpass.getpass("FSS 密码 (不回显): ")
    return user, pw

def main():
    USERNAME, PASSWORD = get_credentials()
    state_path = os.environ.get('FSS_STATE', 'D:/workbuddy/报销/fss_state.json')
    shot_path = os.environ.get('FSS_SHOT', 'D:/workbuddy/报销/登录后.png')

    with sync_playwright() as p:
        b = p.chromium.launch(channel='msedge', headless=True)
        ctx = b.new_context(ignore_https_errors=True, user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        pg = ctx.new_page()

        pg.goto('https://fss.sinopec.com/sso/fsso.jsp?sys=ers', timeout=60000)
        pg.wait_for_timeout(4000)

        # 填明文，让 JS 自己处理加密（勿预加密，否则双重 Base64 失败）
        pg.fill('#j_username', USERNAME)
        pg.wait_for_timeout(300)
        pg.fill('#j_password', PASSWORD)
        pg.wait_for_timeout(300)

        yzm = pg.evaluate("""() => {
            const bar = document.getElementById('yzm1Bar');
            return bar ? getComputedStyle(bar).display : 'NO_EL';
        }""")
        print("验证码区:", yzm)

        # 点击登录按钮触发页面自身 validateLoginFields（含 Base64 加密）
        clicked = pg.evaluate("""() => {
            const btn = document.querySelector('button.loginBt, input[type=submit]');
            if (!btn) return 'NO_BTN';
            btn.click();
            return 'clicked:' + btn.tagName;
        }""")
        print("click:", clicked)

        pg.wait_for_timeout(12000)
        ok = False
        for i in range(8):
            pg.wait_for_timeout(3000)
            u = pg.url
            print(f"[{i}] URL:", u[:250])
            if 'fss.sinopec.com' in u and 'auth' not in u and 'sso' not in u and 'cas' not in u:
                ok = True
                break

        body = pg.content()
        print("页面标题:", pg.title()[:100])
        import re
        m = re.search(r'(认证失败|errorDivMsg[^<]*<[^>]*>[^<]{0,60})', body)
        if m:
            print("状态提示:", m.group(0)[:150])
            sys.exit(1)
        if ok:
            pg.screenshot(path=shot_path, full_page=False)
            ctx.storage_state(path=state_path)
            print(f"== 登录成功，会话已保存到 {state_path} ==")
        else:
            print("== 未能确认登录成功（可能仍在跳转或失败）==")
            sys.exit(2)
        b.close()

if __name__ == '__main__':
    main()
