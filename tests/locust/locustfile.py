import logging

from locust import HttpUser, SequentialTaskSet, task, between

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    # filename="logs/root.log",
    encoding="utf-8",
    filemode="a",
)
logger = logging.getLogger(__name__)


class BuildingFlow(SequentialTaskSet):
    def on_start(self):
        # log in first
        self.login()


    def login(self):
        resp = self.client.get("/accounts/login/")
        csrftoken = resp.cookies["csrftoken"]
        logger.info("Logging in the user %s", self.user)

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": f"{self.user.host}/accounts/login/",
            "Origin": self.user.host,
            "X-CSRFToken": csrftoken,
        }

        payload = {
            # "username": "test10@gmail.com", 
            # "password": "HelloWorld1234",  # Move to env file
            ,
            "csrfmiddlewaretoken": csrftoken,
        }

        with self.client.post(
            "/accounts/login/",
            data=payload,
            headers=headers,
            # name="Do Login",
            catch_response=True
        ) as login_resp:
            if login_resp.status_code != 200:
                # what did we send?
                logging.error("=== REQUEST ===")
                logging.error("Headers: %s", login_resp.request.headers)
                # request.body will be a bytestring
                logging.error("Body: %s", login_resp.request.body)
                
                # what did we get back?
                logging.error("=== RESPONSE ===")
                logging.error("Status code: %s", login_resp.status_code)
                logging.error("Response headers: %s", login_resp.headers)
                # this is the full HTML of your 500 page
                logging.error("Response body: %s", login_resp.text)

                login_resp.failure(f"Login endpoint returned {login_resp.status_code}")

    @task
    def view_buildings(self):
        # Step 1: list all buildings
        resp = self.client.get("/")
        # Optionally pick one at random or parse list for IDs
        # Here we assume we'll create a new one, so no ID yet
        self.csrf = resp.cookies["csrftoken"]



class WebsiteUser(HttpUser):
    tasks = [BuildingFlow]
    wait_time = between(1, 5)
    


