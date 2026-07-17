# Inference JSON Resolution Design

JSON復元のfallbackでentityと`List<T>`を決定する。明示role、直前出力型、許可時のtext entity推論の順で解決し、entity不明時はmetadataを生成しない。
