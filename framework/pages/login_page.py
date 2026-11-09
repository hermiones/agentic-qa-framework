from .base_page import BasePage


class LoginPage(BasePage):
    path = "/login"

    def __init__(self, page):
        super().__init__(page)
        self.username = page.get_by_test_id("username")
        self.password = page.get_by_test_id("password")
        self.captcha = page.get_by_test_id("captcha")
        self.captcha_image = page.get_by_test_id("captcha-image")
        self.sign_in = page.get_by_test_id("sign-in")
        self.error = page.get_by_test_id("login-error")

    def submit(self, username: str, password: str, captcha: str = ""):
        self.username.fill(username)
        self.password.fill(password)
        self.captcha.fill(captcha)
        self.sign_in.click()
        return self
