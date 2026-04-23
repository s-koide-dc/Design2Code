# -*- coding: utf-8 -*- 
# src/file_operations/file_operations.py

import os
import shutil
from typing import Dict, Any
from src.utils.retry_utils import retry_with_backoff

class FileOperations:
    """ファイル操作を担当する独立モジュール"""
    
    def __init__(self, action_executor):
        self.ae = action_executor

    @retry_with_backoff(max_retries=3)
    def create_file(self, context: Dict[str, Any], parameters: Dict[str, Any]) -> Dict[str, Any]:
        filename = self.ae._get_entity_value(parameters.get("filename"))
        content = self.ae._get_entity_value(parameters.get("content", ""))
        
        if not filename:
            context["action_result"] = {"status": "error", "message": "ファイル名が指定されていません。"}
            return context
            
        # File size limit check (10MB)
        MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
        if len(content.encode('utf-8')) > MAX_FILE_SIZE:
            context["action_result"] = {"status": "error", "message": f"ファイルサイズが制限を超えています。最大{MAX_FILE_SIZE // (1024*1024)}MBまで対応しています。"}
            return context
            
        path = self.ae._safe_join(filename)
        if not path:
            context["action_result"] = {"status": "error", "message": "無効なパスです。"}
            return context

        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            context["action_result"] = {"status": "success", "message": f"ファイル '{filename}' を作成しました。"}
        except PermissionError as e:
            context["action_result"] = self.ae._handle_exception_with_patterns(e, f"ファイル '{filename}' の作成権限がありません。")
        except OSError as e:
            context["action_result"] = self.ae._handle_exception_with_patterns(e, f"ファイルの作成中にOSエラーが発生しました: {e}")
        except Exception as e:
            context["action_result"] = self.ae._handle_exception_with_patterns(e, f"ファイルの作成に失敗しました: {e}")
            
        return context

    @retry_with_backoff(max_retries=3)
    def append_file(self, context: Dict[str, Any], parameters: Dict[str, Any]) -> Dict[str, Any]:
        filename = self.ae._get_entity_value(parameters.get("filename"))
        content = self.ae._get_entity_value(parameters.get("content", ""))
        
        if not filename:
             context["action_result"] = {"status": "error", "message": "ファイル名が指定されていません。"}
             return context
             
        path = self.ae._safe_join(filename)
        if not path or not os.path.exists(path):
             context["action_result"] = {"status": "error", "message": "ファイルが見つかりません。"}
             return context

        # Check file size after append
        MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
        try:
            current_size = os.path.getsize(path)
            new_content_size = len(content.encode('utf-8'))
            if current_size + new_content_size > MAX_FILE_SIZE:
                context["action_result"] = {"status": "error", "message": f"ファイルサイズが制限を超えています。最大{MAX_FILE_SIZE // (1024*1024)}MBまで対応しています。"}
                return context
        except OSError as e:
            context["action_result"] = self.ae._handle_exception_with_patterns(e, f"ファイルサイズの確認に失敗しました: {e}")
            return context

        try:
            with open(path, 'a', encoding='utf-8') as f:
                f.write("\n" + content)
            context["action_result"] = {"status": "success", "message": f"ファイル '{filename}' に追記しました。"}
        except PermissionError as e:
            context["action_result"] = self.ae._handle_exception_with_patterns(e, f"ファイル '{filename}' への追記権限がありません。")
        except OSError as e:
            context["action_result"] = self.ae._handle_exception_with_patterns(e, f"ファイルの追記中にOSエラーが発生しました: {e}")
        except Exception as e:
            context["action_result"] = self.ae._handle_exception_with_patterns(e, f"ファイルの追記に失敗しました: {e}")
            
        return context

    def delete_file(self, context: Dict[str, Any], parameters: Dict[str, Any]) -> Dict[str, Any]:
        filename = self.ae._get_entity_value(parameters.get("filename"))
        if not filename:
             context["action_result"] = {"status": "error", "message": "ファイル名が指定されていません。"}
             return context
             
        path = self.ae._safe_join(filename)

        if not path or not os.path.exists(path):
             context["action_result"] = {"status": "error", "message": "ファイルが見つかりません。"}
             return context

        try:
            if os.path.isdir(path):
                shutil.rmtree(path)
                context["action_result"] = {"status": "success", "message": f"ディレクトリ '{filename}' を削除しました。"}
            else:
                os.remove(path)
                context["action_result"] = {"status": "success", "message": f"ファイル '{filename}' を削除しました。"}
        except PermissionError as e:
            context["action_result"] = self.ae._handle_exception_with_patterns(e, f"'{filename}' を削除する権限がありません。")
        except OSError as e:
            context["action_result"] = self.ae._handle_exception_with_patterns(e, f"削除中にOSエラーが発生しました: {e}")
        except Exception as e:
            context["action_result"] = self.ae._handle_exception_with_patterns(e, f"削除に失敗しました: {e}")
            
        return context

    def read_file(self, context: Dict[str, Any], parameters: Dict[str, Any]) -> Dict[str, Any]:
        filename = self.ae._get_entity_value(parameters.get("filename"))
        if not filename:
            context["action_result"] = {"status": "error", "message": "ファイル名が指定されていません。"}
            return context
            
        path = self.ae._safe_join(filename)
        if not path:
             context["action_result"] = {"status": "error", "message": "無効なパスです。"}
             return context
             
        try:
            if not os.path.exists(path):
                raise FileNotFoundError(f"ファイル '{filename}' が見つかりません。")

            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            context["action_result"] = {
                "status": "success", 
                "message": f"ファイル '{filename}' の内容:\n{content[:500]}...",
                "content": content
            }
        except FileNotFoundError as e:
            context["action_result"] = self.ae._handle_exception_with_patterns(e, f"ファイル '{filename}' が見つかりません。")
        except PermissionError as e:
            context["action_result"] = self.ae._handle_exception_with_patterns(e, f"ファイル '{filename}' の読み込み権限がありません。")
        except UnicodeDecodeError as e:
            context["action_result"] = self.ae._handle_exception_with_patterns(e, f"ファイル '{filename}' の文字コードが不明です。UTF-8で保存されているか確認してください。")
        except Exception as e:
            context["action_result"] = self.ae._handle_exception_with_patterns(e, f"ファイルの読み込みに失敗しました: {e}")
            
        return context

    def list_dir(self, context: Dict[str, Any], parameters: Dict[str, Any]) -> Dict[str, Any]:
        dir_name = self.ae._get_entity_value(parameters.get("directory", "."))
        path = self.ae._safe_join(dir_name)
        
        if not path:
             context["action_result"] = {"status": "error", "message": "無効なパスです。"}
             return context

        if not os.path.isdir(path):
             context["action_result"] = {"status": "error", "message": "ディレクトリが見つかりません。"}
             return context

        try:
            items = os.listdir(path)
            message = f"ディレクトリ '{dir_name}' の内容:\n" + "\n".join(items[:20])
            context["action_result"] = {"status": "success", "message": message}
        except PermissionError as e:
            context["action_result"] = self.ae._handle_exception_with_patterns(e, f"ディレクトリ '{dir_name}' の一覧取得権限がありません。")
        except Exception as e:
            context["action_result"] = self.ae._handle_exception_with_patterns(e, f"一覧の取得に失敗しました: {e}")
            
        return context

    @retry_with_backoff(max_retries=3)
    def move_file(self, context: Dict[str, Any], parameters: Dict[str, Any]) -> Dict[str, Any]:
        source = self.ae._get_entity_value(parameters.get("source_filename"))
        destination = self.ae._get_entity_value(parameters.get("destination_filename"))
        
        if not source or not destination:
            context["action_result"] = {"status": "error", "message": "移動元または移動先が指定されていません。"}
            return context
            
        src_path = self.ae._safe_join(source)
        dst_path = self.ae._safe_join(destination)
        
        if not src_path or not dst_path:
            context["action_result"] = {"status": "error", "message": "無効なパスです。"}
            return context
            
        try:
            dst_dir = os.path.dirname(dst_path)
            if not os.path.exists(dst_dir):
                os.makedirs(dst_dir, exist_ok=True)
            
            shutil.move(src_path, dst_path)
            context["action_result"] = {"status": "success", "message": f"'{source}' を '{destination}' に移動しました。"}
        except FileNotFoundError as e:
            context["action_result"] = self.ae._handle_exception_with_patterns(e, f"移動元ファイル '{source}' が見つかりません。")
        except PermissionError as e:
            context["action_result"] = self.ae._handle_exception_with_patterns(e, f"'{source}' を移動する権限がないか、移動先に書き込み権限がありません。")
        except Exception as e:
            context["action_result"] = self.ae._handle_exception_with_patterns(e, f"移動に失敗しました: {e}")
            
        return context

    @retry_with_backoff(max_retries=3)
    def copy_file(self, context: Dict[str, Any], parameters: Dict[str, Any]) -> Dict[str, Any]:
        source = self.ae._get_entity_value(parameters.get("source_filename"))
        destination = self.ae._get_entity_value(parameters.get("destination_filename"))
        
        if not source or not destination:
            context["action_result"] = {"status": "error", "message": "コピー元またはコピー先が指定されていません。"}
            return context
            
        src_path = self.ae._safe_join(source)
        dst_path = self.ae._safe_join(destination)
        
        if not src_path or not dst_path:
            context["action_result"] = {"status": "error", "message": "無効なパスです。"}
            return context
            
        try:
            dst_dir = os.path.dirname(dst_path)
            if not os.path.exists(dst_dir):
                os.makedirs(dst_dir, exist_ok=True)
            
            if os.path.isdir(src_path):
                shutil.copytree(src_path, dst_path)
            else:
                shutil.copy2(src_path, dst_path)
            context["action_result"] = {"status": "success", "message": f"'{source}' を '{destination}' にコピーしました。"}
        except FileNotFoundError as e:
            context["action_result"] = self.ae._handle_exception_with_patterns(e, f"コピー元ファイル '{source}' が見つかりません。")
        except PermissionError as e:
            context["action_result"] = self.ae._handle_exception_with_patterns(e, f"'{source}' をコピーする権限がないか、コピー先に書き込み権限がありません。")
        except Exception as e:
            context["action_result"] = self.ae._handle_exception_with_patterns(e, f"コピーに失敗しました: {e}")
            
        return context
