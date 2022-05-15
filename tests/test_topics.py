from hnread import topics


def test_check_topic_exist():
    assert "top" in topics.Topic._member_names_


def test_get_topic_from_str():
    assert topics.Topic("topstories")
