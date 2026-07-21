from backend.schemas import RegisterOperatorAccountRequest


TEST_PASSWORD = "secret123"


def authenticate_test_client(
    client,
    service,
    identity=None,
    account_name="H1 API Test Operator",
):
    if identity is not None:
        account_name = identity.account_name
    account = service.repository.get_operator_account_by_name(account_name)
    if account is None:
        identity = service.register_operator_account(
            RegisterOperatorAccountRequest(
                account_name=account_name,
                password=TEST_PASSWORD,
                confirm_password=TEST_PASSWORD,
            )
        )
    response = client.post(
        "/api/manual-dispatch/auth/login",
        json={"account_name": account_name, "password": TEST_PASSWORD},
    )
    if response.status_code != 200:
        raise AssertionError(
            f"Test client login failed with {response.status_code}: {response.text}"
        )
    return response.json()
