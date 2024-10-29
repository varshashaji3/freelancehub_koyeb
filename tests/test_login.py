from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))

login_data = [
    {"email": "admin@gmail.com", "password": "Admin@12", "expected_url": "http://127.0.0.1:8000/administrator/admin_view/"},
    {"email": "ava.robinson@gmail.com", "password": "Ava@1234", "expected_url": "http://127.0.0.1:8000/freelancer/freelancer_view/"},
    {"email": "samuel@gmail.com", "password": "Sam@1234", "expected_url": "http://127.0.0.1:8000/client/client_view/"},
    {"email": "samuel@gmail.com", "password": "Sam@1235", "expected_url": "http://127.0.0.1:8000/login/"},  # Invalid credentials
]

try:
    for credentials in login_data:
        driver.get("http://127.0.0.1:8000/login/")

        email_input = WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.NAME, "mail"))  
        )
        password_input = WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.NAME, "pass"))  
        )

        email_input.clear()
        password_input.clear()

        email_input.send_keys(credentials['email'])
        password_input.send_keys(credentials['password'])

        password_input.send_keys(Keys.RETURN)

        time.sleep(2) 

        if driver.current_url == credentials['expected_url'] and driver.current_url!="http://127.0.0.1:8000/login/":
            print(f"Test Paased.Login successful for {credentials['email']}.")
            time.sleep(2)
            logout_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.LINK_TEXT, "Logout"))  
            )
            logout_button.click()
        else:
            print(f"Test failed. Incorrect Credentials.")


finally:
    driver.quit()
