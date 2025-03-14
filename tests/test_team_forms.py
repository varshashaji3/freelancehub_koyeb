from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time

# Add these color constants at the top with the other imports
GREEN = '\033[92m'
RED = '\033[91m'
RESET = '\033[0m'

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
try:
    # Login first
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
    
    # Wait for login to complete and verify
    try:
        WebDriverWait(driver, 10).until(EC.url_contains('/freelancer/freelancer_view/'))
        print(f"{GREEN}Logged in successfully.{RESET}")
    except Exception as e:
        print(f"{RED}Login failed: {str(e)}{RESET}")
        raise

    # Navigate to teams page and wait for it to load
    driver.get('http://127.0.0.1:8000/freelancer/manage-team/')
    try:
        create_team_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, 'createTeamBtn'))
        )
        create_team_btn.click()
    except Exception as e:
        print(f"{RED}Failed to find or click create team button: {str(e)}{RESET}")
        raise

    # Test case 1: Try with existing team name
    try:
        team_name_input = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, 'teamNameInput'))
        )
        team_name_input.send_keys('hi')
        
        time.sleep(5) 
        WebDriverWait(driver, 10).until(
            lambda x: x.find_element(By.ID, 'submitButton').get_attribute('disabled') == 'true'
        )
        close_button = driver.find_element(By.ID, 'closeButton')
        submit_button = driver.find_element(By.ID, 'submitButton')
        if submit_button.get_attribute('disabled'):
            print(f'{GREEN}Test Passed: Submit button is disabled for existing team name.{RESET}')
            close_button.click()
            driver.refresh()
        else:
            print(f'{RED}Test Failed: Submit button should be disabled for existing team name.{RESET}')
    
        
        time.sleep(5) 
        create_team_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, 'createTeamBtn'))
        )
        create_team_btn.click()
        
        team_name_input = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, 'teamNameInput'))
        )
        team_name_input.send_keys('New Test Team')
        
        # Wait for validation to occur using explicit wait
        WebDriverWait(driver, 10).until(
            lambda x: x.find_element(By.ID, 'submitButton').get_attribute('disabled') != 'true'
        )
        
        submit_button = driver.find_element(By.ID, 'submitButton')
        if not submit_button.get_attribute('disabled'):
            submit_button.click()
            WebDriverWait(driver, 10).until(EC.url_contains('/manage-team/'))
            
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, 'createTeamBtn'))
            )
            print(f'{GREEN}Test Passed: Team created successfully with new name.{RESET}')
        else:
            print(f'{RED}Test Failed: Submit button should be enabled for new team name.{RESET}')
    except Exception as e:
        print(f"{RED}Failed during team creation tests: {str(e)}{RESET}")
        raise

except Exception as e:
    print(f"{RED}Test Failed with error: {str(e)}{RESET}")
    raise  # Re-raise the exception to see the full stack trace

finally:
    driver.quit() 