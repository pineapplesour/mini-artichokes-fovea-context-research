from shared_platform.products import PRODUCT_PROFILES, get_product


def test_required_product_profiles_exist():
    assert {"islam", "buddhist", "catholic", "hindu", "tcm", "simli"}.issubset(PRODUCT_PROFILES)


def test_product_profiles_point_to_expected_databases():
    assert get_product("islam").db_path.name == "islam.sqlite3"
    assert get_product("buddhist").db_path.name == "buddhist.sqlite3"
    assert get_product("catholic").db_path.name == "catholic.sqlite3"
    assert get_product("hindu").db_path.name == "hindu.sqlite3"
    assert get_product("tcm").db_path.name == "tcm.sqlite3"
    assert get_product("simli").db_path.name == "psych.sqlite"


def test_product_profiles_declare_languages_for_future_i18n():
    assert get_product("tcm").languages == ("ko", "en")
    assert get_product("simli").languages == ("ko", "en")
    assert get_product("buddhist").languages == ("ko", "en")
    assert get_product("catholic").languages == ("ko", "en")
    assert get_product("hindu").languages == ("ko", "en")
    assert get_product("islam").languages == (
        "en",
        "ko",
        "ar",
        "pa",
        "ur",
        "bn",
        "id",
        "ms",
        "fa",
        "tr",
        "sw",
    )
