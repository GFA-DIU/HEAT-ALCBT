import os
import re
import logging
import queue

from dotenv import load_dotenv

from locust import HttpUser, SequentialTaskSet, task, between

# ---------------------------------------------------------
# 1. Configure Python Logging
# ---------------------------------------------------------
# By default, Locust installs handlers for the 'root' logger
# and all 'locust.*' loggers. Any logging.* calls here will
# appear in Locust’s output (stderr) or in a log file if --logfile is used.
logging.basicConfig(
    level=logging.INFO,  # Set minimum level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

logger = logging.getLogger(__name__)  # Our module-level logger

load_dotenv()

credential_queue = queue.Queue()
LOAD_TESTING_PASSWORD = os.getenv("LOAD_TESTING_PASSWORD")
for i in range(10, 20):
    credential_queue.put((f"test1{i:02d}@test.com", LOAD_TESTING_PASSWORD))

# ---------------------------------------------------------

## Remote
EPD1 = "007525c3-8381-4219-bc05-ea974d033187"
EPD2 = "00a1026a-7af3-4611-a86e-2ae81a3927cc"
EPD3 = "0af4a07e-6789-41d1-b3f6-c30dcc1be35b"

## Local
# EPD1 = "00d63a33-55a9-4d21-8de9-3f310345eb96"
# EPD2 = "004845fa-9ab5-494d-b2dc-faff8c39bd13"
# EPD3 = "0200fe27-b083-4e30-a7f7-0ef98fd8f373"


class LoginAndViewRoot(SequentialTaskSet):
    """
    A SequentialTaskSet that:
      1. Logs in via Django Allauth (/accounts/login/),
      2. Visits the root endpoint ("/") as an authenticated user,
      3. Logs key events and failures.
    """

    def on_start(self):
        """
        Called when a Locust user starts this TaskSet.
        We GET the login page to grab CSRF, then POST credentials.
        """
        # -------------------------------
        # Step 1: GET the login page
        # -------------------------------
        logger.info("User %s: Fetching login page to obtain CSRF token", self.user.environment.runner.user_count)
        login_page_response = self.client.get("/accounts/login/", name="Load Login Page")

        csrftoken = login_page_response.cookies["csrftoken"]
        if not csrftoken:
            logger.error(
                "User %s: CSRF token not found on login page (status_code=%s)",
                self.user.environment.runner.user_count,
                login_page_response.status_code,
            )
            login_page_response.failure("Unable to find CSRF token on login page")
            return

        logger.info("User %s: CSRF token extracted successfully", self.user.environment.runner.user_count)

        # -------------------------------
        # Step 2: POST credentials
        # -------------------------------
        login_payload = {
            "login": self.user.username,
            "password": self.user.password,
            "csrfmiddlewaretoken": csrftoken,
        }
        # Django expects Referer header for CSRF validation
        headers = {"Referer": f"{self.client.base_url}/accounts/login/"}
        
        logger.info("User %s: Using username: %s", self.user.environment.runner.user_count, self.user.username)

        logger.info("User %s: Submitting login form", self.user.environment.runner.user_count)
        with self.client.post(
            "/accounts/login/",
            data=login_payload,
            headers=headers,
            name="Submit Login",
            allow_redirects=False,  # We want to inspect the initial redirect
            catch_response=True
        ) as login_response:

            if login_response.status_code != 302:
                logger.error(
                    "User %s: Login failed (status_code=%s)",
                    self.user.environment.runner.user_count,
                    login_response.status_code,
                )
                login_response.failure(f"Login failed: status_code={login_response.status_code}")
            else:
                logger.info("User %s: Login successful, redirected to %s",
                            self.user.environment.runner.user_count,
                            login_response.headers.get("Location", "<no-location>"))
                login_response.success()

    @task
    def view_root(self):
        """
        As a logged-in user, GET "/" and confirm status_code=200.
        """
        logger.info("User %s: Accessing root endpoint '/'", self.user.environment.runner.user_count)
        with self.client.get(
            "/",
            name="Access Root",
            catch_response=True,
        ) as root_response:

            if root_response.status_code != 200:
                logger.error(
                    "User %s: Unexpected status_code when accessing '/': %s",
                    self.user.environment.runner.user_count,
                    root_response.status_code,
                )
                root_response.failure(f"Unexpected status_code for '/': {root_response.status_code}")
            else:
                logger.info("User %s: Successfully accessed '%s' (status_code=200)", self.user.environment.runner.user_count, root_response.headers.get("Location", ""))
                logger.info("Response Body:\\%s", root_response.text[-10:])
                root_response.success()


    @task
    def create_building(self):
        """
        After visiting '/', GET the 'new building' form, extract CSRF,
        then POST the building data to create a new Building.
        """
        # ---------------------------------------------------------
        # Step 3: GET the new-building form to retrieve CSRF token
        # ---------------------------------------------------------
        logger.info("User %s: Loading new building form at '/building/_new'", self.user.environment.runner.user_count)
        form_response = self.client.get("/building/_new", name="Load New Building Form")

        csrftoken = form_response.cookies["csrftoken"]
        if not csrftoken:
            logger.error(
                "CSRF token not found on new building form (status_code=%s)",
                form_response.status_code,
            )
            form_response.failure("Unable to find CSRF token on new building form")
            return

        logger.info("User %s: CSRF token for building form extracted successfully", self.user.environment.runner.user_count)

        # ---------------------------------------------------------
        # Step 4: POST the new building data
        # ---------------------------------------------------------
        building_payload = {
            "name": "Test Building",
            "action": "general_information",
            "category": 10,
            "climate_zone": "composite",
            "reference_period": 50,
            "total_floor_area": 350,
            "country": 2,
            "submit": "Submit",
            "csrfmiddlewaretoken": csrftoken,
        }
        # headers = {"Referer": f"{self.client.base_url}/building/_new"}
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": f"{self.user.host}/building/_new",
            "Origin": self.user.host,
            "X-CSRFToken": csrftoken,
        }

        logger.info("User %s: Submitting new building form", self.user.environment.runner.user_count)
        with self.client.post(
            "/building/_new",
            data=building_payload,
            headers=headers,
            name="Submit New Building",
            allow_redirects=False,  # We expect a 302 redirect on success
            catch_response=True,
        ) as create_response:

            # ---------------------------------------------------------
            # Step 5: Check for expected redirect (302) or success code
            # ---------------------------------------------------------
            if create_response.status_code != 302 and create_response.status_code != 200:
                logger.error(
                    "User %s: New building creation failed (status_code=%s)",
                    self.user.environment.runner.user_count,
                    create_response.status_code,
                )
                create_response.failure(f"Unexpected status: {create_response.status_code}")
            else:
                logger.info(
                    "User %s: New building creation succeeded (status_code=%s)",
                    self.user.environment.runner.user_count,
                    create_response.status_code,
                )
                logger.info("User %s: Find next: %s", self.user.environment.runner.user_count, create_response.headers.get("Location"))
                
                location = create_response.headers.get("Location", "")
                logger.info("User %s: New building creation succeeded (status_code=%s), redirect to %s",
                            self.user.environment.runner.user_count,
                            create_response.status_code, location)

                # Use a regex to grab the UUID portion of "/building/<uuid>/"
                match = re.search(r"/building/([0-9a-fA-F\-]+)/", location)
                if match:
                    self.building_id = match.group(1)
                    logger.info("User %s: Extracted building_id: %s", self.user.environment.runner.user_count, self.building_id)
                else:
                    # If for some reason regex fails, mark this step as failure.
                    logger.error("User %s: Could not parse building ID from Location header: %s", self.user.environment.runner.user_count, location)
                    create_response.failure(f"Failed to parse building ID from redirect: {location}")
                    return

                create_response.success()


    @task
    def create_assembly(self):
        """
        Using the building ID captured above, GET the 'new assembly' page
        for that building, extract CSRF, then POST the new assembly data.
        URL pattern: /boq/<building_id>/_new?simulation=False
        """
        # Make sure we have a building_id from the previous step
        if not hasattr(self, "building_id"):
            logger.error("No building_id found on self; skipping create_assembly.")
            return

        new_assembly_path = f"/boq/{self.building_id}/_new?simulation=False"
        logger.info("User %s: Loading new assembly form at '%s'", self.user.environment.runner.user_count, new_assembly_path)
        
        form_response = self.client.get(
            new_assembly_path,
            name="Load New Assembly Form",
        )

        csrftoken = form_response.cookies.get("csrftoken")

        ## Do a page step
        page_2_path = new_assembly_path+"page=2&dimension=None&childcategory=&subcategory=&category=&search_query=&country=&type=&simulation=False"

        form_response = self.client.get(
            page_2_path,
            name="Load Page 2 Form",
        )
        logger.info("User %s: Loaded the second page of EPDs", self.user.environment.runner.user_count)

        csrftoken = form_response.cookies.get("csrftoken")
        
        ## Add Products
        assembly_payload = {
            "name": "Test Assembly",
            "comment": "Test Assembly created by Locust",
            "reporting_life_cycle": 50,
            "action": "form_submission",
            f"material_{EPD1}_description_": "Test",
            f"material_{EPD1}_category_": "1",
            f"material_{EPD1}_quantity_": "600",
            f"material_{EPD1}_unit_": "m3",
            
            f"material_{EPD2}_description_": "Test",
            f"material_{EPD2}_category_": "1",
            f"material_{EPD2}_quantity_": "600",
            f"material_{EPD2}_unit_": "m2",
            
            F"material_{EPD3}_description_": "Test",
            F"material_{EPD3}_category_": "1",
            F"material_{EPD3}_quantity_": "600",
            F"material_{EPD3}_unit_": "m3",

            "csrfmiddlewaretoken": csrftoken,
        }

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": f"{self.user.host}/{new_assembly_path}",
            "Origin": self.user.host,
            "X-CSRFToken": csrftoken,
        }
        
        with self.client.post(
            new_assembly_path,
            data=assembly_payload,
            headers=headers,
            name="Submit New Assembly",
            allow_redirects=False,  # likely a 302 redirect on success
            catch_response=True,
        ) as assembly_response:
            # Check for redirect or success code
            if assembly_response.status_code not in (200, 302):
                logger.error(
                    "User %s: New assembly creation failed (status_code=%s)",
                    self.user.environment.runner.user_count,
                    assembly_response.status_code,
                )
                assembly_response.failure(
                    f"Unexpected status: {assembly_response.status_code}"
                )
            else:
                logger.info(
                    "User %s: New assembly creation succeeded (status_code=%s) for building %s",
                    self.user.environment.runner.user_count,
                    assembly_response.status_code,
                    self.building_id,
                )
                location = assembly_response.headers.get("Location", "")
                logger.info("Redirection to %s", location)
                assembly_response.success()


    @task
    def view_building(self):
        """
        As a logged-in user, GET "/" and confirm status_code=200.
        """
        logger.info("User %s: Accessing root endpoint '/'", self.user.environment.runner.user_count)
        with self.client.get(
            f"/building/{self.building_id}/",
            name="View Building",
            catch_response=True,
        ) as root_response:

            if root_response.status_code != 200:
                logger.error(
                    "User %s: Unexpected status_code when accessing '/': %s",
                    self.user.environment.runner.user_count,
                    root_response.status_code,
                )
                root_response.failure(f"Unexpected status_code for '/': {root_response.status_code}")
            else:
                logger.info("User %s: Successfully accessed '%s' (status_code=200)", self.user.environment.runner.user_count, root_response.headers.get("Location", ""))
                logger.info("Response Body:\\%s", root_response.text[-10:])
                root_response.success()


    ## Second Assembly creation
    @task
    def create_assembly2(self):
        """
        Using the building ID captured above, GET the 'new assembly' page
        for that building, extract CSRF, then POST the new assembly data.
        URL pattern: /boq/<building_id>/_new?simulation=False
        """
        # Make sure we have a building_id from the previous step
        if not hasattr(self, "building_id"):
            logger.error("No building_id found on self; skipping create_assembly.")
            return

        new_assembly_path = f"/boq/{self.building_id}/_new?simulation=False"
        logger.info("User %s: Loading new assembly form at '%s'", self.user.environment.runner.user_count, new_assembly_path)
        
        form_response = self.client.get(
            new_assembly_path,
            name="Load New Assembly Form 2",
        )

        csrftoken = form_response.cookies.get("csrftoken")

        ## Do a page step
        page_2_path = new_assembly_path+"page=2&dimension=None&childcategory=&subcategory=&category=&search_query=&country=&type=&simulation=False"

        form_response = self.client.get(
            page_2_path,
            name="Load Page 2 Form",
        )
        logger.info("User %s: Loaded the second page of EPDs", self.user.environment.runner.user_count)

        csrftoken = form_response.cookies.get("csrftoken")
        
        ## Add Products
        assembly_payload = {
            "name": "Test Assembly",
            "comment": "Test Assembly created by Locust",
            "reporting_life_cycle": 50,
            "action": "form_submission",
            f"material_{EPD1}_description_": "Test",
            f"material_{EPD1}_category_": "1",
            f"material_{EPD1}_quantity_": "600",
            f"material_{EPD1}_unit_": "m3",
            
            f"material_{EPD2}_description_": "Test",
            f"material_{EPD2}_category_": "1",
            f"material_{EPD2}_quantity_": "600",
            f"material_{EPD2}_unit_": "m2",
            
            F"material_{EPD3}_description_": "Test",
            F"material_{EPD3}_category_": "1",
            F"material_{EPD3}_quantity_": "600",
            F"material_{EPD3}_unit_": "m3",

            "csrfmiddlewaretoken": csrftoken,
        }

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": f"{self.user.host}/{new_assembly_path}",
            "Origin": self.user.host,
            "X-CSRFToken": csrftoken,
        }
        
        with self.client.post(
            new_assembly_path,
            data=assembly_payload,
            headers=headers,
            name="Submit New Assembly 2",
            allow_redirects=False,  # likely a 302 redirect on success
            catch_response=True,
        ) as assembly_response:
            # Check for redirect or success code
            if assembly_response.status_code not in (200, 302):
                logger.error(
                    "User %s: New assembly creation failed (status_code=%s)",
                    self.user.environment.runner.user_count,
                    assembly_response.status_code,
                )
                assembly_response.failure(
                    f"Unexpected status: {assembly_response.status_code}"
                )
            else:
                logger.info(
                    "User %s: New assembly creation succeeded (status_code=%s) for building %s",
                    self.user.environment.runner.user_count,
                    assembly_response.status_code,
                    self.building_id,
                )
                location = assembly_response.headers.get("Location", "")
                logger.info("Redirection to %s", location)
                assembly_response.success()


    @task
    def view_building2(self):
        """
        As a logged-in user, GET "/" and confirm status_code=200.
        """
        logger.info("User %s: Accessing root endpoint '/'", self.user.environment.runner.user_count)
        with self.client.get(
            f"/building/{self.building_id}/",
            name="View Building 2",
            catch_response=True,
        ) as root_response:

            if root_response.status_code != 200:
                logger.error(
                    "User %s: Unexpected status_code when accessing '/': %s",
                    self.user.environment.runner.user_count,
                    root_response.status_code,
                )
                root_response.failure(f"Unexpected status_code for '/': {root_response.status_code}")
            else:
                logger.info("User %s: Successfully accessed '%s' (status_code=200)", self.user.environment.runner.user_count, root_response.headers.get("Location", ""))
                logger.info("Response Body:\\%s", root_response.text[-10:])
                root_response.success()

class WebsiteUser(HttpUser):
    """
    Defines a Locust user that runs the LoginAndViewRoot sequence.
    """
    tasks = [LoginAndViewRoot]
    wait_time = between(1, 3)  # Pause after each full sequence
    host = "https://beat-alcbt.gggi.org"
    # host = "http://127.0.0.1:8000"
    # HttpUser (and its underlying client) automatically persists session cookies
    # between requests by default. :contentReference[oaicite:3]{index=3}


    def __init__(self, environment, *args, **kwargs):
        super().__init__(environment, *args, **kwargs)
        try:
            # pop one unique credential for this user
            self.username, self.password = credential_queue.get_nowait()
        except queue.Empty:
            # if you spawn more than 10 users, stop the extras
            logger.error("No more credentials available – stopping this user")
            raise Exception


# call: locust -f tests/locust/locustfile.py       --host https://beat-alcbt.gggi.org