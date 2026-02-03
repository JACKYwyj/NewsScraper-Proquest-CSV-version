import pandas as pd
import time
import random
import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ================= 配置区域 =================
# 触发重爬的关键词（反爬提示语）
ROBOT_MSG = "Our internal systems think you might be a Robot"


# ===========================================

def get_credentials():
    """弹出输入框获取账号密码"""
    root = tk.Tk()
    root.withdraw()  # 隐藏主窗口

    # 获取账号
    user = simpledialog.askstring("身份验证", "请输入您的登录账号:")
    if not user:
        return None, None

    # 获取密码 (show='*' 会将输入显示为星号)
    pwd = simpledialog.askstring("身份验证", "请输入您的登录密码:", show='*')
    if not pwd:
        return None, None

    return user, pwd


def get_user_file():
    """弹出文件选择框"""
    root = tk.Tk()
    root.withdraw()
    file_path = filedialog.askopenfilename(
        title="请选择包含新闻链接的 CSV 文件",
        filetypes=[("CSV Files", "*.csv")]
    )
    return file_path


def setup_driver():
    """初始化浏览器驱动"""
    chrome_options = Options()
    chrome_options.add_argument('--start-maximized')
    # 规避检测配置
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument(
        f'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{random.randint(118, 128)}.0.0.0 Safari/537.36')

    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        })
        return driver
    except Exception as e:
        messagebox.showerror("驱动错误", f"无法启动浏览器，请检查Chrome是否为最新版。\n错误信息: {e}")
        sys.exit()


def random_smooth_scroll(driver):
    """防封：平滑滚动"""
    try:
        total_height = driver.execute_script("return document.body.scrollHeight")
        if total_height < 1000: return
        target_height = int(total_height * random.uniform(0.3, 0.6))
        current = 0
        step = random.randint(200, 400)
        while current < target_height:
            current += step
            driver.execute_script(f"window.scrollTo(0, {current});")
            time.sleep(random.uniform(0.1, 0.3))
    except:
        pass


def handle_popups(driver):
    """处理常见的弹窗"""
    pop_selectors = ['button[aria-label="Close"]', '.modal-header .close', '#onetrust-accept-btn-handler']
    for s in pop_selectors:
        try:
            driver.find_element(By.CSS_SELECTOR, s).click()
        except:
            pass


def auto_login(driver, first_url, username, password):
    """登录模块 (接收动态账号密码)"""
    print(f"--- 正在尝试登录 (账号: {username}) ---")
    driver.get(first_url)
    wait = WebDriverWait(driver, 20)
    try:
        time.sleep(3)
        # 勾选框
        try:
            checks = driver.find_elements(By.CSS_SELECTOR, 'input[type="checkbox"]')
            for cb in checks:
                if not cb.is_selected(): driver.execute_script("arguments[0].click();", cb)
        except:
            pass

        # 输入账号
        user_field = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'input[type="text"], input[name*="user"], #username')))
        user_field.clear()
        user_field.send_keys(username)

        # 输入密码
        pass_field = driver.find_element(By.CSS_SELECTOR, 'input[type="password"]')
        pass_field.clear()
        pass_field.send_keys(password)

        # 点击登录
        try:
            btn = driver.find_element(By.CSS_SELECTOR, 'button[type="submit"], input[type="submit"]')
            driver.execute_script("arguments[0].click();", btn)
        except:
            pass_field.submit()

        print(">>> 登录信息已提交，等待跳转...")
    except Exception as e:
        print(f"登录过程可能出现异常 (不影响如果已经有Cookie): {e}")
    time.sleep(10)  # 给予充足的重定向时间


def get_text(driver, url):
    """抓取单条正文，含重试机制"""
    max_retries = 2
    for attempt in range(max_retries):
        try:
            driver.get(url)
            time.sleep(random.uniform(2, 4))

            # 检测反爬
            if ROBOT_MSG in driver.page_source:
                print(f"  ⚠️ 触发反爬验证，暂停 30 秒...")
                time.sleep(30)
                continue

            random_smooth_scroll(driver)
            handle_popups(driver)

            # 优先级选择器
            selectors = ["#documentBody", ".text-container", ".article-body", ".fullText"]
            content = ""
            for s in selectors:
                try:
                    el = driver.find_element(By.CSS_SELECTOR, s)
                    if el.is_displayed() and len(el.text) > 50:
                        content = el.text.strip()
                        break
                except:
                    continue

            if content: return content

            # 兜底：抓取所有P标签
            paras = driver.find_elements(By.TAG_NAME, 'p')
            full_p = "\n".join([p.text for p in paras if len(p.text) > 40])
            if len(full_p) > 100: return full_p

        except Exception as e:
            print(f"  Err: {e}")
            time.sleep(2)

    return "抓取失败：多次重试未找到正文"


def check_repair(text):
    """检查是否需要爬取"""
    if pd.isna(text) or str(text).strip() == "": return True
    if ROBOT_MSG in str(text): return True
    if "抓取失败" in str(text): return True
    return False


def main():
    print("==========================================")
    print("      Factiva/新闻 通用断点续爬工具 V3")
    print("==========================================")

    # 1. 获取账号密码
    username, password = get_credentials()
    if not username or not password:
        print("用户取消输入或输入为空，程序退出。")
        return

    # 2. 选择文件
    input_path = get_user_file()
    if not input_path:
        print("未选择文件，程序退出。")
        return

    # 生成输出文件名
    dir_name = os.path.dirname(input_path)
    base_name = os.path.basename(input_path)
    file_name_no_ext = os.path.splitext(base_name)[0]
    output_path = os.path.join(dir_name, f"{file_name_no_ext}_已处理.xlsx")

    print(f"当前用户: {username}")
    print(f"任务文件: {base_name}")
    print(f"结果存档: {os.path.basename(output_path)}")

    # 3. 读取 CSV 并处理
    try:
        try:
            df = pd.read_csv(input_path, encoding='gbk')
        except:
            df = pd.read_csv(input_path, encoding='utf-8')
    except Exception as e:
        print(f"读取CSV失败: {e}")
        return

    # 4. 排序
    if 'PubDate' in df.columns:
        print("正在按 PubDate 从旧到新排序...")
        df['PubDate_Dt'] = pd.to_datetime(df['PubDate'], errors='coerce')
        df = df.sort_values(by='PubDate_Dt', ascending=True).reset_index(drop=True)
    else:
        print("警告：未找到 PubDate 列，将按原始顺序处理。")

    # 初始化 Full_Text
    if 'Full_Text' not in df.columns:
        df['Full_Text'] = None

    # 5. 断点续爬逻辑
    if os.path.exists(output_path):
        print("检测到上次的存档文件，正在恢复进度...")
        try:
            df_existing = pd.read_excel(output_path)
            # 只有当行数一致时才安全恢复
            if len(df_existing) == len(df):
                df['Full_Text'] = df_existing['Full_Text']
                completed_count = df['Full_Text'].apply(lambda x: not check_repair(x)).sum()
                print(f"已恢复 {completed_count} 条历史记录。")
            else:
                # 行数不一致时，尝试按位置覆盖前N条
                print("⚠️ 存档与源文件行数不符，仅尝试覆盖匹配部分...")
                min_len = min(len(df), len(df_existing))
                df.loc[:min_len - 1, 'Full_Text'] = df_existing.iloc[:min_len]['Full_Text'].values
        except Exception as e:
            print(f"恢复进度失败: {e}，将重新开始。")

    # 6. 生成任务队列
    todo_indices = [i for i, row in df.iterrows() if check_repair(row['Full_Text'])]
    total_tasks = len(todo_indices)

    print(f"当前剩余任务数: {total_tasks} / {len(df)}")

    if total_tasks == 0:
        print("🎉 所有数据已爬取完毕！无需操作。")
        input("按回车键退出...")
        return

    # 7. 启动爬虫
    driver = setup_driver()
    try:
        # 先登录 (传入手动输入的账号密码)
        first_url = df.iloc[todo_indices[0]]['DocumentUrl']
        auto_login(driver, first_url, username, password)

        for i, idx in enumerate(todo_indices):
            row = df.iloc[idx]
            url = row['DocumentUrl']
            title = str(row.get('Title', 'No Title'))[:20]

            print(f"进度 [{i + 1}/{total_tasks}] | ID: {idx} | 处理中: {title}...")

            text = get_text(driver, url)
            df.at[idx, 'Full_Text'] = text

            # 存盘策略
            if (i + 1) % 10 == 0:
                print("--- 自动保存进度 ---")
                df.to_excel(output_path, index=False)
                if (i + 1) % 50 == 0:
                    time.sleep(10)
            else:
                time.sleep(random.uniform(3, 6))

    except KeyboardInterrupt:
        print("\n用户手动停止！正在保存当前进度...")
    except Exception as e:
        print(f"\n发生严重错误: {e}")
    finally:
        print("正在最终保存文件...")
        if 'PubDate_Dt' in df.columns:
            df_save = df.drop(columns=['PubDate_Dt'])
        else:
            df_save = df

        df_save.to_excel(output_path, index=False)
        if 'driver' in locals():
            driver.quit()
        print(f"\n处理完成！最终文件已保存至:\n{output_path}")
        input("按回车键退出...")


if __name__ == "__main__":
    main()