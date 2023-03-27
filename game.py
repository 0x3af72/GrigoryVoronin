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

    def get_move(self):

        # wrong turn? dont want to confuse anything
        if not self.board.turn == self.my_turn:
            raise Exception("Wrong turn!")

        # get top lines from lichess
        print(f"CURRENT FEN: {self.board.fen()}")
        self.driver_analysis.get(f"https://lichess.org/analysis/standard/{self.board.fen()}")
        time.sleep(self.game_options["wait_eval_duration"])
        passed = False
        while not passed: # stale element cuz it keeps changing
            try:
                moves = [elem.get_attribute("data-board").split("|")[1] for elem in self.driver_analysis.find_elements(By.XPATH, "//span[@data-move-index='0']")]
                if len(moves) >= 1:
                    passed = True
            except StaleElementReferenceException as e:
                print(f"STALE ELEMENT: {e}")
        print(self.game_options["all_best"])
        if self.game_options["all_best"]:
            move = moves[0]
        else:
            # get evals
            evals = []
            while len(evals) < len(moves):
                evals = [ev.text for ev in self.driver_analysis.find_elements(By.TAG_NAME, "strong")][:5]

            # get available moves
            available_moves = [
                m for idx, m in enumerate(moves)
                if (float(evals[idx].replace("#", "")) * (-1 if not self.my_turn else 1) * (1000 if "#" in evals[idx] else 1))\
                >= self.game_options["lowest_eval"]
            ]

            if available_moves:

                # if can capture, capture
                move = ""
                for m in available_moves:
                    if "x" in self.board.san(chess.Move.from_uci(m)):
                        print("must do:", m)
                        move = m
                
                # otherwise take random
                if not move:
                    move = random.choice(available_moves)
            else:
                move = moves[0]
            print(move)
            print(f"CURRENT EVAL: {evals[moves.index(move)]}")

        # return chosen move
        return self.san_to_uci(move)
    
    def san_to_uci(self, move_san):
        return self.board.parse_san(move_san).uci()
    
    def push_move(self, move):
        self.board.push(chess.Move.from_uci(move))

    def push_san(self, move_san):
        self.board.push(self.board.parse_san(move_san))