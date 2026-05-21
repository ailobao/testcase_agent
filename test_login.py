# test_login.py
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By


# 读取 AI 生成的 Excel
df = pd.read_excel("data/tpshop商城_登录_004.xlsx", sheet_name="测试用例")

driver = webdriver.Edge()
driver.get("https://your-tpshop-url.com/login")

for _, row in df.iterrows():
    username = row["用户名"]
    password = row["密码"]
    code = row["验证码"]
    expected = row["预期结果"]

    # 输入
    driver.find_element(By.ID, "username").clear()
    driver.find_element(By.ID, "username").send_keys(username)
    driver.find_element(By.ID, "password").clear()
    driver.find_element(By.ID, "password").send_keys(password)
    driver.find_element(By.ID, "verify_code").clear()
    driver.find_element(By.ID, "verify_code").send_keys(code)
    driver.find_element(By.ID, "login_btn").click()

    # 断言
    assert expected in driver.page_source

    # 回写结果（可选）
    row["实际结果"] = "PASS"

driver.quit()