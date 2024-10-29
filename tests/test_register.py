from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))

registration_data = [
    {
        "fname": "Mary",
        "lname": "Doe",
        "email": "mary.doe@gmail.com",  
        "password": "Mary@123",
        "repassword": "Mary@123",
        "expected_url": "http://127.0.0.1:8000/add_user_type/65"  
    },
    {
        "fname": "Noah",
        "lname": "Wilson",
        "email": "noah.wilson@gmail.com",  
        "password": "Noah@123",
        "repassword": "Noah@123",
        "expected_url": "http://127.0.0.1:8000/register/"
    }
]

try:
    for data in registration_data:
        driver.get("http://127.0.0.1:8000/register/")

        fname_input = WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.NAME, "fname"))
        )
        lname_input = WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.NAME, "lname"))
        )
        email_input = WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.NAME, "email"))
        )
        password_input = WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.NAME, "password"))
        )
        repassword_input = WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.NAME, "repassword"))
        )

        fname_input.clear()
        lname_input.clear()
        email_input.clear()
        password_input.clear()
        repassword_input.clear()

        fname_input.send_keys(data['fname'])
        lname_input.send_keys(data['lname'])
        email_input.send_keys(data['email'])
        password_input.send_keys(data['password'])
        repassword_input.send_keys(data['repassword'])

        driver.find_element(By.ID, "subbtn").click()
        time.sleep(3)
        if driver.current_url == data['expected_url'] and "add_user_type" in data['expected_url']:
            
            driver.find_element(By.ID, "create-account-btn").click()
            time.sleep(3)

            if driver.current_url == "http://127.0.0.1:8000/login/":
                print(f"Test Paased :Registration successful for {data['email']}")
            else:
                print(f"Test failed for {data['email']}")
        elif driver.current_url == data['expected_url'] and data['expected_url'] == "http://127.0.0.1:8000/register/":
            print(f"Test passed for existing email {data['email']}")
        else:
            print(f"Test failed for {data['email']}")
        

finally:
    driver.quit()
