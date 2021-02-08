from tomodachi import aws_sns_sqs

aws_sns_sqs(
    "topic", filter_policy={"currency": ["SEK", "EUR", "USD", "GBP", "CNY"], "amount": [{"numeric": [">=", 2]}]}
)
aws_sns_sqs(
    "topic",
    filter_policy={
        "store": ["example_corp"],
        "event": ["order_cancelled"],
        "encrypted": [False],
        "customer_interests": [
            "basketball",
            "baseball",
        ],
    },
)
aws_sns_sqs(
    "topic",
    filter_policy={
        "legacy_id": [1, 2, 3],
    },
)
aws_sns_sqs("topic", filter_policy={"customer_interests": ["rugby", "football", "baseball"]})
aws_sns_sqs(
    "topic",
    filter_policy={
        "inconsistant_policy_attribute": [4711, False],
        "inconsistant_policy_attribute_2": [4711, True],
    },
)
aws_sns_sqs(
    "topic",
    filter_policy={
        "store": ["example_corp"],
        "event": [{"anything-but": "order_cancelled"}],
        "customer_interests": [
            "rugby",
            "football",
            "baseball",
        ],
        "price_usd": [{"numeric": [">=", 100]}],
    },
)
aws_sns_sqs(
    "topic",
    filter_policy={
        "store": [{"exists": True}],
    },
)
aws_sns_sqs(
    "topic",
    filter_policy={
        "customer_interests": [{"anything-but": ["rugby", "tennis"]}],
        "price_usd": [{"numeric": [">", 100]}],
        "negative_value": [{"numeric": ["<", 0]}],
    },
)
aws_sns_sqs(
    "topic",
    filter_policy={
        "customer_interests": [{"prefix": "bas"}],
        "price_usd": [{"numeric": ["=", 301.5]}],
        "price": [{"anything-but": [100, 500]}],
        "total": [{"numeric": [">", 0, "<=", 150]}],
    },
)
aws_sns_sqs(
    "topic",
    filter_policy={
        "my_interest": [{"prefix": "bas"}],
        "my_value": [1, 2, 3, 4711, 3.14],
        "my_anything": [{"anything-but": [0, 4, 3.14]}],
        "my_total": [{"numeric": [">", 0, "<=", 150]}],
        "my_list": [None, "nope", False],
    },
)
aws_sns_sqs(
    "topic",
    filter_policy={
        "my_list": [None, "nope", False],
        "my_list_two": [None],
    },
)
aws_sns_sqs(
    "topic",
    filter_policy={
        "dev.tomodachi.mypy.filter_key": ["a", "b", "c", 4711],
    },
)
