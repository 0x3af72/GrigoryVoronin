import selenium
from selenium import webdriver
from selenium.webdriver import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.support import expected_conditions as EC

import chess

import time
import random

class Game:

    def __init__(self, my_turn, driver_analysis, game_options):
        self.board = chess.Board()
        self.my_turn = my_turn
        self.driver_analysis = driver_analysis
        self.game_options = game_options

    def store_line(self, lines, elem):

        # get move text
        move = elem.get_attribute("data-board").split("|")[1]

        # get and store the entire line (parent)
        lines[move] = []
        line_elem = elem.find_element(By.XPATH, "..")
        for i in range(0, 6): # 6 means 3 moves ahead
            lines[move].append(line_elem.find_element(By.XPATH, f"//span[@data-move-index='{i + 1}']").text)

        # return
        return move

    def get_move(self, lichess_wait):

        # wrong turn? dont want to confuse anything
        if not self.board.turn == self.my_turn:
            raise Exception("Wrong turn!")

        # get top lines from lichess
        print(f"CURRENT FEN: {self.board.fen()}")
        self.driver_analysis.get(f"https://lichess.org/analysis/standard/{self.board.fen()}")
        print(lichess_wait)
        time.sleep(lichess_wait)
        passed = False
        lines = {}
        while not passed: # handle stale element cuz it keeps changing
            try:
                driver.implicitly_wait(0)
                moves = [self.store_line(lines, elem) for elem in self.driver_analysis.find_elements(By.XPATH, "//span[@data-move-index='0']")]
                if len(moves) >= 1:
                    passed = True
            except StaleElementReferenceException as e:
                print(f"STALE ELEMENT: {e}")
        driver.implicitly_wait(2)

        # get evals
        evals = []
        while len(evals) < len(moves):
            evals = [
                float(ev.text.replace("#", "")) * (-1 if not self.my_turn else 1) * (1000 if "#" in ev.text else 1)
                for ev in self.driver_analysis.find_elements(By.TAG_NAME, "strong")[:5]
            ]

        # find move to play
        if self.game_options["all_best"]:
            move = moves[0]
        else:

            # get available moves
            available_moves = [
                m for idx, m in enumerate(moves)
                if evals[idx] >= self.game_options["lowest_eval"]
            ]

            if available_moves:

                # if can capture, capture
                move = ""
                for m in available_moves:
                    if "x" in self.board.san(chess.Move.from_uci(m)):
                        print("must do:", m)
                        move = m
                        break
                
                # otherwise take random
                if not move:
                    move = random.choice(available_moves)
            else:
                move = moves[0]
                print("forced")
            print(move)
            print(f"CURRENT EVAL: {evals[moves.index(move)]}")

        # return chosen move
        return self.san_to_uci(move), lines[move]
    
    def san_to_uci(self, move_san):
        return self.board.parse_san(move_san).uci()
    
    def push_move(self, move):
        self.board.push(chess.Move.from_uci(move))

    def push_san(self, move_san):
        self.board.push(self.board.parse_san(move_san))