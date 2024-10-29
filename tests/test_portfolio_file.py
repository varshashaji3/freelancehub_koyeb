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
    email_input.send_keys('noah.wilson@gmail.com')
    password_input = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.NAME, 'pass'))
    )
    password_input.send_keys('Noah@123')
    password_input.send_keys(Keys.RETURN)
    WebDriverWait(driver, 10).until(EC.url_contains('/freelancer/freelancer_view/'))
    print("Logged in successfully. Current URL:", driver.current_url)
    driver.get('http://127.0.0.1:8000/freelancer/template_list/')
    
    template_card = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.CLASS_NAME, 'card'))
    )

    use_template_button = template_card.find_element(By.XPATH, ".//button[contains(@onclick, 'openModal')]")
    use_template_button.click()

    upload_modal = WebDriverWait(driver, 10).until(
        EC.visibility_of_element_located((By.ID, 'uploadModal'))
    )

    file_input = upload_modal.find_element(By.ID, 'file')
    file_input.send_keys(r"C:\Users\LENOVO\Downloads\MC_Assignment 2.docx")
    submit_button = upload_modal.find_element(By.ID, 'subbtn')

    time.sleep(1)

    if not submit_button.is_enabled():
        driver.execute_script("alert('Test Case 1 Passed: DOCX correctly rejected.');")
    else:
        driver.execute_script("alert('Test Case 1 Failed: DOCX rejection failed.');")

    alert = WebDriverWait(driver, 10).until(EC.alert_is_present())
    print(alert.text)
    time.sleep(3)
    alert.accept()

    close_button = upload_modal.find_element(By.ID, 'close')
    close_button.click()

    WebDriverWait(driver, 10).until(EC.invisibility_of_element_located((By.ID, 'uploadModal')))

    driver.get('http://127.0.0.1:8000/freelancer/template_list/')
    template_card = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.CLASS_NAME, 'card'))
    )
    use_template_button = template_card.find_element(By.XPATH, ".//button[contains(@onclick, 'openModal')]")
    use_template_button.click()

    upload_modal = WebDriverWait(driver, 10).until(
        EC.visibility_of_element_located((By.ID, 'uploadModal'))
    )

    file_input = upload_modal.find_element(By.ID, 'file')
    file_input.send_keys(r"C:\Users\LENOVO\Downloads\Varsha Shaji_INT MCA_Amal Jyothi College.pdf")
    submit_button = upload_modal.find_element(By.ID, 'subbtn')
    submit_button.click()

    try:
        WebDriverWait(driver, 10).until(EC.url_matches(r'http://127\.0\.0\.1:8000/freelancer/process_resume/\d+/'))
        print('Test Case 2 Passed: PDF uploaded successfully.')
    except:
        print('Test Case 2 Failed: PDF upload failed.')

    time.sleep(2)

except Exception as e:
    print(f"Test Failed: {e}")

finally:
    driver.quit()
