# -*- coding: utf-8 -*-
import os
import json
import sys
from typing import List, Dict, Any

# Ensure project root is in path
sys.path.append(os.getcwd())

from src.config.config_manager import ConfigManager
from src.code_synthesis.method_store import MethodStore
from src.vector_engine.vector_engine import VectorEngine

def get_expanded_system_methods():
    """汎用性の高いシステムおよびSQL関連メソッドのリストを返す"""
    methods = [
        # --- SQL / Database (Dapper-like Generic Patterns) ---
        {
            "name": "Query",
            "class": "System.Data.IDbConnection",
            "return_type": "IEnumerable<T>",
            "params": [
                {"name": "cnn", "type": "IDbConnection", "role": "target"}, 
                {"name": "sql", "type": "string", "role": "sql"},
                {"name": "param", "type": "object", "role": "param"}
            ],
            "code": "{cnn}.Query<T>({sql}, {param})",
            "definition": "public static IEnumerable<T> Query<T>(this IDbConnection cnn, string sql, object param = null)",
            "tags": ["sql", "database", "query", "select", "dapper"],
            "has_side_effects": True,
            "usings": ["System.Data", "Dapper"],
            "role": "FETCH"
        },
        {
            "name": "Execute",
            "class": "System.Data.IDbConnection",
            "return_type": "int",
            "params": [
                {"name": "cnn", "type": "IDbConnection", "role": "target"}, 
                {"name": "sql", "type": "string", "role": "sql"},
                {"name": "param", "type": "object", "role": "param"}
            ],
            "code": "{cnn}.Execute({sql}, {param})",
            "definition": "public static int Execute(this IDbConnection cnn, string sql, object param = null)",
            "tags": ["sql", "database", "execute", "insert", "update", "delete", "dapper", "save", "persist"],
            "has_side_effects": True,
            "usings": ["System.Data", "Dapper"],
            "role": "PERSIST"
        },
        {
            "name": "QueryFirstOrDefault",
            "class": "System.Data.IDbConnection",
            "return_type": "T",
            "params": [
                {"name": "cnn", "type": "IDbConnection", "role": "target"}, 
                {"name": "sql", "type": "string", "role": "sql"},
                {"name": "param", "type": "object", "role": "param"}
            ],
            "code": "{cnn}.QueryFirstOrDefault<T>({sql}, {param})",
            "definition": "public static T QueryFirstOrDefault<T>(this IDbConnection cnn, string sql, object param = null)",
            "tags": ["sql", "database", "query", "single", "dapper"],
            "has_side_effects": True,
            "usings": ["System.Data", "Dapper"],
            "role": "FETCH"
        },

        # --- System.IO (Core Patterns) ---
        {
            "name": "WriteAllTextAsync",
            "class": "System.IO.File",
            "return_type": "Task",
            "params": [
                {"name": "path", "type": "string", "role": "path"}, 
                {"name": "contents", "type": "string", "role": "content"}
            ],
            "code": "await System.IO.File.WriteAllTextAsync({path}, {contents})",
            "tags": ["file", "io", "write", "file_save", "async"],
            "has_side_effects": True,
            "role": "PERSIST"
        },
        {
            "name": "WriteAllText",
            "class": "System.IO.File",
            "return_type": "void",
            "params": [
                {"name": "path", "type": "string", "role": "path"}, 
                {"name": "contents", "type": "string", "role": "content"}
            ],
            "code": "System.IO.File.WriteAllText({path}, {contents})",
            "tags": ["file", "io", "write", "file_save", "export"],
            "has_side_effects": True,
            "role": "PERSIST"
        },
        {
            "name": "ReadAllTextAsync",
            "class": "System.IO.File",
            "return_type": "Task<string>",
            "params": [{"name": "path", "type": "string", "role": "path"}],
            "code": "await System.IO.File.ReadAllTextAsync({path})",
            "tags": ["file", "io", "read", "load", "async"],
            "has_side_effects": True,
            "role": "FETCH"
        },
        {
            "name": "ReadAllText",
            "class": "System.IO.File",
            "return_type": "string",
            "params": [{"name": "path", "type": "string", "role": "path"}],
            "code": "System.IO.File.ReadAllText({path})",
            "tags": ["file", "io", "read", "load"],
            "has_side_effects": True,
            "role": "FETCH"
        },
        {
            "name": "Exists",
            "class": "System.IO.File",
            "return_type": "bool",
            "params": [{"name": "path", "type": "string", "role": "path"}],
            "code": "System.IO.File.Exists({path})",
            "tags": ["file", "check", "exists"],
            "has_side_effects": False,
            "role": "EXISTS"
        },

        # --- HTTP (HttpClient) ---
        {
            "name": "GetStringAsync",
            "class": "System.Net.Http.HttpClient",
            "return_type": "Task<string>",
            "params": [
                {"name": "client", "type": "HttpClient", "role": "target"}, 
                {"name": "requestUri", "type": "string", "role": "url"}
            ],
            "code": "await {client}.GetStringAsync({requestUri})",
            "tags": ["http", "network", "get", "download"],
            "usings": ["System.Net.Http"],
            "role": "FETCH"
        },

        # --- Console ---
        {
            "name": "WriteLine",
            "class": "System.Console",
            "return_type": "void",
            "params": [{"name": "value", "type": "object", "role": "content"}],
            "code": "System.Console.WriteLine({value})",
            "tags": ["console", "output", "display", "print"],
            "role": "DISPLAY"
        },
        {
            "name": "Write",
            "class": "System.Console",
            "return_type": "void",
            "params": [
                {"name": "format", "type": "string", "role": "content"},
                {"name": "arg0", "type": "object", "role": "param"}
            ],
            "code": "System.Console.Write({format}, {arg0})",
            "tags": ["console", "output", "display", "print"],
            "role": "DISPLAY"
        },

        # --- LINQ (Essential Tools) ---
        {
            "name": "Where",
            "class": "System.Linq.Enumerable",
            "return_type": "IEnumerable<T>",
            "params": [
                {"name": "source", "type": "IEnumerable<T>", "role": "target"}, 
                {"name": "predicate", "type": "Func<T, bool>", "role": "predicate"}
            ],
            "code": "{source}.Where({predicate})",
            "tags": ["linq", "filter", "search"],
            "usings": ["System.Linq"],
            "role": "TRANSFORM"
        },
        {
            "name": "Select",
            "class": "System.Linq.Enumerable",
            "return_type": "IEnumerable<TResult>",
            "params": [
                {"name": "source", "type": "IEnumerable<T>", "role": "target"}, 
                {"name": "selector", "type": "Func<T, TResult>", "role": "selector"}
            ],
            "code": "{source}.Select({selector})",
            "tags": ["linq", "map", "transform"],
            "usings": ["System.Linq"],
            "role": "TRANSFORM"
        },
        {
            "name": "ToList",
            "class": "System.Linq.Enumerable",
            "return_type": "List<T>",
            "params": [{"name": "source", "type": "IEnumerable<T>", "role": "target"}],
            "code": "{source}.ToList()",
            "tags": ["linq", "convert"],
            "usings": ["System.Linq"],
            "role": "TRANSFORM"
        },
        {
            "name": "Any",
            "class": "System.Linq.Enumerable",
            "return_type": "bool",
            "params": [{"name": "source", "type": "IEnumerable<T>", "role": "target"}],
            "code": "{source}.Any()",
            "tags": ["linq", "check", "empty"],
            "usings": ["System.Linq"],
            "role": "TRANSFORM"
        },

        # --- Resilience & Logic Patterns (Generic API) ---
        {
            "name": "Retry",
            "class": "Common.Resilience.Utils",
            "return_type": "T",
            "params": [
                {"name": "action", "type": "Func<T>", "role": "action"},
                {"name": "maxRetries", "type": "int", "role": "param"}
            ],
            "code": "Common.Resilience.Utils.Retry({action}, {maxRetries})",
            "definition": "public static T Retry<T>(Func<T> action, int maxRetries = 3)",
            "tags": ["retry", "recovery", "resilience", "error handling"],
            "has_side_effects": True,
            "role": "INVOKE"
        },
        {
            "name": "GetEnvironmentVariable",
            "class": "System.Environment",
            "return_type": "string",
            "params": [{"name": "variable", "type": "string", "role": "param"}],
            "code": "System.Environment.GetEnvironmentVariable({variable})",
            "tags": ["env", "config", "system"],
            "has_side_effects": False,
            "role": "FETCH"
        },

        # --- JSON (System.Text.Json) ---
        {
            "name": "Deserialize",
            "class": "System.Text.Json.JsonSerializer",
            "return_type": "T",
            "params": [{"name": "json", "type": "string", "role": "content"}],
            "code": "System.Text.Json.JsonSerializer.Deserialize<T>({json})",
            "tags": ["json", "deserialize", "parse"],
            "usings": ["System.Text.Json"],
            "role": "TRANSFORM"
        },
        {
            "name": "Serialize",
            "class": "System.Text.Json.JsonSerializer",
            "return_type": "string",
            "params": [{"name": "value", "type": "object", "role": "content"}],
            "code": "System.Text.Json.JsonSerializer.Serialize({value})",
            "tags": ["json", "serialize", "format"],
            "usings": ["System.Text.Json"],
            "role": "TRANSFORM"
        }
    ]
    return methods

def sync():
    print("Starting MethodStore synchronization...")
    config = ConfigManager()
    vector_engine = VectorEngine()
    store = MethodStore(config, vector_engine=vector_engine)
    
    # 既存の項目を完全にクリア (強制リセット)
    store.items = []
    store.id_to_index = {}
    
    # 1. Harvest結果 (resources/method_store_final.json) の読み込み
    harvest_path = 'resources/method_store_final.json'
    if os.path.exists(harvest_path):
        print(f"Loading harvested methods from {harvest_path}...")
        try:
            with open(harvest_path, 'r', encoding='utf-8') as f:
                # UTF-16等の可能性を考慮した読み込みは呼び出し側(PowerShell)で済んでいる前提だが、
                # ここでも最低限のパースを行う
                content = f.read()
                start_idx = content.find('{')
                if start_idx != -1:
                    data = json.loads(content[start_idx:])
                    harvested_methods = data.get('methods', [])
                    print(f"Adding {len(harvested_methods)} harvested methods...")
                    for m in harvested_methods:
                        store.add_method(m, overwrite=True)
        except Exception as e:
            print(f"Error loading harvest results: {e}")

    # 2. 追加のシステムメソッド定義
    print("Adding predefined system methods...")
    system_methods = get_expanded_system_methods()
    for m in system_methods:
        if "id" not in m:
            m["id"] = f"sys.{m['class'].lower()}.{m['name'].lower()}"
        m["origin"] = "system"
        if "summary" not in m:
            m["summary"] = f"Standard library method: {m['name']} in {m['class']}"
        store.add_method(m, overwrite=True)
    
    # 3. 保存
    store.save()
    print(f"Synchronization complete. Total methods: {len(store.items)}")

if __name__ == "__main__":
    sync()
