# -*- coding: utf-8 -*-

class DummyService:
    def __init__(self, action_executor, name="Default"):
        self.executor = action_executor
        self.name = name

    def perform_action(self, target):
        self.executor.execute({"target": target})
        return f"Action performed on {target} by {self.name}"
