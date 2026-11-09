"""Exception types the classifier understands."""


class BusinessRuleViolation(AssertionError):
    """The product returned a wrong business value: a real product defect."""


class TestDataError(Exception):
    """The test's own data or fixtures are missing or invalid."""

    __test__ = False  # not a pytest test class


class EnvironmentUnavailable(Exception):
    """The system under test (or a dependency) is down or answering 5xx."""
