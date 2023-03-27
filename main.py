import selenium
from selenium import webdriver
from selenium.webdriver import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException
from selenium.webdriver.support import expected_conditions as EC

import json
import time

import game

# paths
EXECUTABLE_PATH = "drivers/chromedriver.exe"
BRAVE_PATH = "C:/Program Files/BraveSoftware/Brave-Browser/Application/brave.exe" # have to install brave for this to work

# load cookies from file
def load_cookies(file):
    with open(file, "r") as r:
        return json.load(r)
    
# get current turn and last move
def turn_state(driver):
    
    # get move elements and current turn
    moves = driver.find_elements(By.XPATH, "//div[contains(@class, 'node')]")
    turn_state = len(moves) % 2 == 0 # true for white and false for black

    # get last move
    passed = False
    num_fails = 0
    while not passed:
        try:
            last_move = [move for move in moves if "selected" in move.get_attribute("class")]
            passed = True
        except StaleElementReferenceException as e:
            num_fails += 1
            print(f"STALE ELEMENT: {e}")
            if num_fails >= 100: # might stale when game ends
                raise e # game might have ended
    
    # last move handling
    if not last_move:
        last_move = None # no last move
    else:
        # icon if exists
        icon = ""
        try:
            driver.implicitly_wait(0) # dont wait at all because might not exist
            icon = last_move[0].find_element(By.TAG_NAME, "span").get_attribute("data-figurine")
        except NoSuchElementException:
            pass

        # get the full move
        if icon == None: # in case of en passant
            icon = ""
        if not "=" in last_move[0].text:
            last_move = icon + last_move[0].text
        else:
            last_move = last_move[0].text + icon
    driver.implicitly_wait(2) # revert back to normal

    return turn_state, last_move

# tile to number
def tile_to_number(tile):
    return f"{ord(tile[0]) - ord('a') + 1}{tile[1]}"

# setup driver
def setup():

    # driver options
    options = webdriver.ChromeOptions()
    options.binary_location = BRAVE_PATH
    prefs = {"profile.default_content_setting_values.notifications": 2} # this disables the screen dimming thing
    options.add_experimental_option("prefs", prefs)
    options.add_experimental_option("excludeSwitches", ["enable-logging"])
    options.add_argument("--log-level=3")
    options.add_argument("--disable-logging")

    # create driver and add cookies
    driver = webdriver.Chrome(service=Service(EXECUTABLE_PATH), options=options)
    options.add_argument("--headless")
    driver_analysis = webdriver.Chrome(service=Service(EXECUTABLE_PATH), options=options)
    driver.implicitly_wait(2)
    driver_analysis.implicitly_wait(2)
    driver.execute_cdp_cmd("Network.enable", {})
    cookies = load_cookies("data/cookies.json") # read cookies here
    for cookie in cookies:
        cookie["sameSite"] = "None" # i do not know why this is necessary
        driver.execute_cdp_cmd("Network.setCookie", cookie)

    # setup the lichess analysis
    driver_analysis.get("https://lichess.org/analysis")
    driver_analysis.find_element(By.XPATH, "//label[@for='analyse-toggle-ceval']").click()
    driver_analysis.execute_script("localStorage['analyse.ceval.multipv'] = '5'")

    return driver, driver_analysis

def start_game(driver, driver_analysis, time_control="3 min"):

    # get chess.com page
    driver.get("https://chess.com/play/online")

    # read game options
    with open("data/options.json", "r") as r:
        game_options = json.load(r)

    # remove chess.com premium ad
    try: 
        driver.find_element(By.XPATH, "//div[@class='icon-font-chess x ui_outside-close-icon']").click()
    except NoSuchElementException:
        pass

    # start the game
    driver.find_element(By.XPATH, "//button[@data-cy='new-game-time-selector-button']").click()
    driver.find_element(By.XPATH, f"//button[contains(text(), '{time_control}')]").click()
    driver.find_element(By.XPATH, "//button[@data-cy='new-game-index-play']").click()

    # fair play button
    try:
        driver.find_element(By.XPATH, "//button[contains(text(), 'I Agree')]").click()
    except NoSuchElementException:
        pass

    # check if white or black
    print("waiting for url change")
    WebDriverWait(driver, 6000).until(lambda driver: "/play/online" not in driver.current_url) # dont read the element too fast
    print("ok changed url")
    time.sleep(2) # dirty fix to wait for webpage to refresh
    my_turn = "white" in driver.find_element(By.XPATH, "//div[contains(@class, 'clock-bottom')]").get_attribute("class")

    # create game object
    game_obj = game.Game(my_turn, driver_analysis, game_options)

    # game loop
    while True:

        # short delay to be safe
        time.sleep(0.2)

        # check if time is super low or already no time
        game_over = False
        try:
            driver.implicitly_wait(0)
            driver.find_element(By.XPATH, "//div[@class='header-title-component']")
            game_over = True
        except NoSuchElementException:
            pass
        driver.implicitly_wait(2)
        my_time = driver.find_elements(By.XPATH, "//span[@data-cy='clock-time']")[1].text.split(":")
        seconds_left = float(my_time[0]) * 60 + float(my_time[1])
        if game_over or seconds_left < 2:
            print("game over")
            return
        
        # get turn state
        turn, last_move = turn_state(driver)

        # play move
        if turn == my_turn:
            
            # push last move
            if last_move:
                game_obj.push_san(last_move)
            
            # get move to play
            to_play = game_obj.get_move()
            game_obj.push_move(to_play)

            # play the move - click the first square
            move_from, move_to = to_play[:2], to_play[2:]
            move_elem = driver.find_element(By.XPATH, f"//div[contains(@class, 'square-{tile_to_number(move_from)}')]")
            WebDriverWait(driver, 10).until(EC.element_to_be_clickable(move_elem))
            move_elem.click()
            
            # click the second square (coordinates)
            move_to_number = tile_to_number(move_to)
            board_elem = driver.find_element(By.TAG_NAME, "chess-board")
            driver.execute_script('arguments[0].scrollIntoView({block: "center"});', board_elem)
            board_width = board_elem.size["width"]
            click_x = board_width / 8 * ((int(move_to_number[0]) if turn else (9 - int(move_to_number[0]))) - 0.5)
            click_y = board_width / 8 * ((int(move_to_number[1]) if not turn else (9 - int(move_to_number[1]))) - 0.5)
            action = ActionChains(driver)
            action.move_to_element_with_offset(board_elem, click_x - board_width / 2, click_y - board_width / 2).click_and_hold().perform()
            time.sleep(0.1)
            action.release().perform()

if __name__ == "__main__":
    driver, driver_analysis = setup()
    while True:
        try:
            input("START GAME...")
            start_game(driver, driver_analysis)
        except Exception as e:
            print(e)

# MAKE FASTER CANT EVEN WIN BLITZ
# 1. test for errors (cant find any moves (moves[0] index error))
# 3. randomize move times
# 4. able to play with friends