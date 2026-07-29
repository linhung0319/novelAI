def pytest_addoption(parser):
    """`--regenerate-golden`：重寫回歸黃金檔而不是比對它。

    刻意做成明確的旗標而不是「檔不存在就自動生成」——自動生成會讓「黃金檔被誤刪」
    與「工具改壞了」變成同一個綠燈。
    """
    parser.addoption(
        "--regenerate-golden",
        action="store_true",
        default=False,
        help="重生 tests/golden/ 下的黃金檔（只在刻意改門檻或訊息時用）",
    )
