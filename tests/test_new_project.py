from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
import time
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
try:
    driver.get('http://127.0.0.1:8000/login/')
    email_input = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.NAME, 'mail'))
    )
    email_input.send_keys('tech.innovations@gmail.com')
    password_input = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.NAME, 'pass'))
    )
    password_input.send_keys('Tech@123')
    password_input.send_keys(Keys.RETURN)
    WebDriverWait(driver, 10).until(EC.url_contains('/client/client_view/'))
    print("Logged in successfully")
    driver.get('http://127.0.0.1:8000/client/add_new_project/')
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, 'project_form')))
    title_input = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.ID, 'title'))
    )
    title_input.send_keys('Test Project')
    description_input = driver.find_element(By.ID, 'description')
    description_input.send_keys('This is a test project description.')
    budget_input = driver.find_element(By.ID, 'budget')
    budget_input.send_keys('5000')
    category_dropdown = Select(driver.find_element(By.ID, 'category'))
    category_dropdown.select_by_visible_text('Web Development')
    end_date_input = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.ID, 'end_date')))
    end_date_input.clear()
    end_date_input.send_keys('20-02-2024')
    end_date_input.send_keys(Keys.TAB)
    file_input = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.ID, 'file')))
    file_input.send_keys('C:/Users/LENOVO/Downloads/openstack.pdf')
    scope_dropdown = Select(driver.find_element(By.ID, 'scope'))
    scope_dropdown.select_by_visible_text('Medium')
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(4)
    submit_button = driver.find_element(By.ID, 'addProject')
    WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.ID, 'addProject'))).click()
    if driver.current_url == 'http://127.0.0.1:8000/client/add_new_project/':
        print('Test passed!New project not aaded beacause of error in form filling!')
    elif driver.current_url == 'http://127.0.0.1:8000/client/project_list/':
        print('Test was successful! New project added')

except Exception as e:
    print(f"Test Failed")

finally:
    time.sleep(3)
    driver.quit()
