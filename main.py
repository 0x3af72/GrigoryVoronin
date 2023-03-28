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
    
# get current turn and move history
def turn_state(driver):

    # clear draw offers if any
    try:
        driver.implicitly_wait(0)
        driver.find_element(By.XPATH, "//button[contains(@class, 'draw-offer-button')]").click()
    except NoSuchElementException:
        pass
    driver.implicitly_wait(2)
    
    # get move elements and current turn
    moves = driver.find_elements(By.XPATH, "//div[contains(@class, 'node')]")
    turn_state = len(moves) % 2 == 0 # true for white and false for black

    # get last move
    last_move = None
    try:
        last_move = driver.find_element(By.XPATH, "//div[contains(@class, 'selected')]")
    except NoSuchElementException:
        pass
    
    # last move handling
    if not last_move:
        last_move = None # no last move
    else:
        # icon if exists
        icon = ""
        try:
            driver.implicitly_wait(0) # dont wait at all because might not exist
            icon = last_move.find_element(By.TAG_NAME, "span").get_attribute("data-figurine")
        except NoSuchElementException:
            pass
        driver.implicitly_wait(2) # revert back to normal

        # get the full move
        if icon == None: # in case of en passant
            icon = ""
        if not "=" in last_move.text:
            last_move = icon + last_move.text
        else:
            last_move = last_move.text + icon

    return turn_state, last_move

# tile to number
def tile_to_number(tile):
    return f"{ord(tile[0]) - ord('a') + 1}{tile[1]}"

# setup driver
def setup():

    # driver options
    options = webdriver.ChromeOptions()
    options.binary_location = BRAVE_PATH
    options.add_experimental_option("prefs", {"profile.default_content_setting_values.notifications": 2})
    options.add_experimental_option("excludeSwitches", ["enable-logging"])
    options.add_argument("--log-level=3")
    options.add_argument("--disable-logging")

    # create driver and add cookies
    driver = webdriver.Chrome(service=Service(EXECUTABLE_PATH), options=options)
    options.add_argument("--headless")
    options.add_experimental_option("prefs", {"disable-gpu-vsync": True})
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

def start_game(driver, driver_analysis, time_control="10 min"):

    # get chess.com page
    driver.implicitly_wait(2)
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
    time.sleep(0.2) # wait for refresh
    my_turn = "white" in driver.find_element(By.XPATH, "//div[contains(@class, 'clock-bottom')]").get_attribute("class")

    # create game object
    game_obj = game.Game(my_turn, driver_analysis, game_options)
    lichess_wait = None # wait time for lichess analysis. longer wait means more accuracy

    # game loop
    while True:

        # short delay to be safe
        time.sleep(0.1)

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
        
        # lichess analysis wait time
        if not lichess_wait:
            lichess_wait = seconds_left / 300 + 0.2
        
        # get turn state
        turn, last_move = turn_state(driver)

        # play move
        if turn == my_turn:
            
            # push last move
            if last_move:
                game_obj.push_san(last_move)
            
            # get move to play
            to_play, has_promote, promote_to = game_obj.get_move(lichess_wait)
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
            time.sleep(0.05)
            action.release().perform()

            # promote if have to
            print("PROMOTE", has_promote)
            print("PROMOTE TO", promote_to)
            if has_promote:
                promote_elem = driver.find_element(By.XPATH, f"//div[@class='promotion-piece {'w' if my_turn else 'b'}{promote_to[0]}']")
                promote_elem.click()

if __name__ == "__main__":
    driver, driver_analysis = setup()
    while True:
        try:
            # input("START GAME...")
            start_game(driver, driver_analysis)
        except Exception as e:
            print(e)

# possible to move faster
# time to wait for lichess is dependent on time control??? try seconds / 300
# 3. randomize move times -> based on accuracy and premove lines?
# 4. able to play with friends
# auto resign when bad eval