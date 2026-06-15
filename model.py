"""
Intersight GUI definitions
"""
import inspect
# pylint: disable=too-many-instance-attributes,too-many-arguments,too-many-locals,too-many-public-methods,broad-exception-raised

import re
import os
import sys
import copy
import time
import json
import pprint
import atexit
import logging
import datetime
import traceback


try:
    from urllib import parse
except ImportError:
    parse = None
from typing import Union, Optional, Mapping, Any, Tuple, List, Callable, Dict
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.common import exceptions
from qali import config
from qali.runtests.options import get_app_options_instance
from qali.util.util import create_hyperlink
from qali.intersight.gui import util
from qali.intersight.gui.model_util import Context
from qali.intersight.gui.model_util import ContextManager
from qali.intersight.gui.model_util import NotificationContextMap
from qali.intersight.gui.component_manager import ComponentManager
from qali.intersight.gui.page_manager import PageManager
from qali.intersight.gui.click_manager import ClickManager
from qali.intersight.gui.input_manager import InputManager
from qali.intersight.gui.select_manager import SelectManager
from qali.intersight.gui.table_manager import TableManager
from qali.intersight.gui.canvas_manager import CanvasManager
from qali.intersight.gui.data_manager import DataManager
from qali.intersight.gui.notification_manager import NotificationManager
from qali.intersight.gui.error_manager import ErrorManager
from qali.intersight.gui.iframe_manager import IframeManager
from qali.intersight.api.model_util import CLOUD_HOSTS
from qali.intersight.gui.util import selenium_settings
from qali.intersight.gui.axe import Axe
from qali.runtests import api
from qali.starship_gui.cli_args_parser import get_cli_args_data
from qali import globals as qali_globals
from qali.util.vault_const import vault

try:
    cli_data_info = get_cli_args_data()
except Exception:
    cli_data_info = {}

RePattern = getattr(re, "Pattern")
# Regex Pattern to check if a string is valid or not [0-9A-Za-z]
VALID_STRING_REGEX = re.compile(r'[a-zA-Z0-9]')


class UrlMatchContext:
    """
        Url matching class definition

        This is used to waiting url context with Intersight GUI wait_ctx method.
    """

    def __init__(self,
                 driver: WebDriver,
                 url: Union[str, RePattern]) -> None:
        """
            init function for url match context

            :param driver: selenium web driver
            :param url:

        """
        self.driver = driver
        self.url = url

    def exist(self) -> bool:
        """
            return True if given url context matched.

            :return: True if given url context matched.

        """
        if isinstance(self.url, RePattern):
            return bool(self.url.search(self.driver.current_url))
        return self.driver.current_url == self.url

    def repr(self) -> str:
        """
            return representation string of url context

            :return: representation string of url context
        """
        if isinstance(self.url, RePattern):
            return str(("url", self.url.pattern))
        return str(("url", self.url))


class IntersightGui:
    """
        Intersight GUI class definition
    """

    def __init__(self,
                 url: str = 'https://qa.starshipcloud.com',
                 username: str = vault.INTERSIGHT_GUI['username'],
                 password: str = vault.INTERSIGHT_GUI['password'],
                 use_sso: bool = False,
                 sign_in: bool = True,
                 create_account: bool = False,
                 region: Optional[str] = None,
                 account_name: Optional[str] = None,
                 account_role: Optional[str] = None,
                 browser_type: str = "chrome",
                 driver_version: Optional[str] = None,
                 chrome_debug_port: Union[str, int, None] = None,
                 headless: bool = False,
                 record_video: bool = False,
                 screenshot_path: Optional[str] = None,
                 download_path: Optional[str] = None,
                 exec_env: str = "local",
                 remote_host: Optional[str] = None,
                 remote_port: Union[str, int, None] = None,
                 http_proxy: Union[str, bool, None] = None,
                 remote_session_name: Optional[str] = None,
                 remote_session_token: Optional[str] = None,
                 remote_session_timeout: Union[str, int] = 1800000,
                 idp_email: Optional[str] = None,
                 ldap_domain: Optional[str] = None,
                 oauth_consent_screen: Optional[bool] = False) -> None:
        """
            constructor of Intersight GUI

            Local Browser Example:
                IntersightGui("https://staging.starshipcloud.com",
                              username="abc@abc.com",
                              password="...",
                              use_sso=False,
                              account_name='my-account',
                              account_role='Account Administrator',
                              browser_type="chrome")


            Selenoid Example:
                IntersightGui("https://staging.starshipcloud.com",
                              username="abc@abc.com",
                              password="...",
                              use_sso=False,
                              account_name='my-account',
                              account_role='Account Administrator',
                              browser_type="chrome",
                              exec_env='selenoid',
                              remote_host='localhost',
                              remote_port='4444')

            Seleniumbox Example:
                IntersightGui("https://staging.starshipcloud.com",
                              username="abc@abc.com",
                              password="...",
                              use_sso=False,
                              account_name='my-account',
                              account_role='Account Administrator',
                              browser_type="chrome",
                              exec_env='seleniumbox'
                              remote_session_token='my-token')
)


            :param url:  Intersight url
            :param username: username to use for login
            :param password: password to use for login
            :param use_sso: Whether to use SSO (Single Sign On) for login.  If False,
                            log in with Cisco domain
            :param sign_in: Whether to sign in to the account
            :param create_account: Whether to create an account if one does not exist
            :param region: the region to create the account with
            :param account_name: account name to use for login
            :param account_role: account role to use for login
            :param idp_email: when use_sso is True, idp_email will be used to navigate to idp portal
            :param ldap_domain: LDAP domain to be set for appliance login
            :param oauth_consent_screen: bool flag to indicate that the login is for oauth consent
                                         screen approval for cx cloud
            :param browser_type: browser type to use for Intersight GUI.  Currently support chrome and firefox
            :param driver_version: Selenium browser driver version.  Applicable to local browser only.
                                   If None, latest is used.  Can overwrite with cli data with driver_version keyword.
            :param chrome_debug_port: chrome browser debug port.  Applicable to local Chrome browser only.
            :param headless: whether to run selenium in headless mode or not
            :param record_video: Set to True to record video.  Applicable only to selenoid or seleniumbox mode
            :param screenshot_path: directory to save screenshots in
            :param download_path: directory to download files to.  Applicable only to local browser
            :param exec_env: environment to run selenium.  Currently support 3 mode: local, selenoid, seleniumbox
            :param remote_host: netloc of remote selenium connection url.
                                Applicable only to selenoid or seleniumbox mode.
            :param remote_port: port of remote selenium connection url.
                                Applicable only to selenoid or seleniumbox mode.
            :param http_proxy: Whether http proxy is needed for remote connection.  Applicable only to selenoid.
            :param remote_session_name: session name to be used for selenoid or seleniumbox.
            :param remote_session_token: token for selenium remote connection.  Applicable only to seleniumbox
            :param remote_session_timeout: session timeout for selenium remote connection.
                                           Applicable only to seleniumbox

            :return None
        """
        self.driver = None

        # register itself to quit at exit of python.
        atexit.register(self.quit)
        if not url:
            raise Exception("url is a required parameter")
        parsed_url = parse.urlparse(url)
        # add region to the url if applicable
        if region and not parsed_url.netloc.startswith(region):
            parsed_url = parsed_url._replace(netloc="{0}.{1}".format(region, parsed_url.netloc))
        # define url_prefix for page navigation
        self.url_prefix = "{0}://{1}".format(parsed_url.scheme, parsed_url.netloc)
        self.url = parsed_url.geturl()
        self._spyfile = getattr(getattr(config, "ucs"), "spyfile")
        self._log_level = logging.INFO
        self.auto_close_notification = True
        self.auto_closed_notifications = []
        self.log_err_notification = True
        self.err_notifications = []

        self.use_sso = use_sso
        self.idp_email = idp_email
        self.ldap_domain = ldap_domain
        self.oauth_consent_screen = oauth_consent_screen
        self.account_name = account_name
        self.account_role = account_role
        self.browser_type = browser_type
        self.driver_version = driver_version
        self.chrome_debug_port = chrome_debug_port
        self.headless = headless
        self.record_video = record_video
        self.screenshot_path = screenshot_path
        self.download_path = download_path
        self.exec_env = exec_env
        self.remote_host = remote_host
        self.remote_port = remote_port
        self.http_proxy = http_proxy
        self.remote_session_name = remote_session_name
        self.remote_session_token = remote_session_token
        self.remote_session_timeout = remote_session_timeout
        self.coverage_capture_threshold = 600  # 10 minutes

        self.accessibility_options = '{runOnly: ["wcag2a", "wcag21a"]}'
        # overwrite with command line arguments
        self.update_from_cli_data(cli_data_info)

        if self.remote_session_name is None and 'this_testsuite' in api:
            if hasattr(api['this_testsuite'], 'name'):
                test_case = getattr(api['this_testsuite'], "this_testcase", None)
                if test_case:
                    self.remote_session_name = api['this_testsuite'].name + "/" + test_case.name
                else:
                    self.remote_session_name = api['this_testsuite'].name

        if self.exec_env == 'local':
            self.selenium_settings = selenium_settings.LocalSeleniumSetting(
                browser_type=self.browser_type,
                headless=self.headless,
                driver_version=self.driver_version,
                chrome_debug_port=self.chrome_debug_port,
                download_path=self.download_path,
                log=self.log)
        elif self.exec_env == "selenoid":
            self.selenium_settings = selenium_settings.SeleniodSeleniumSetting(
                browser_type=self.browser_type,
                headless=self.headless,
                host=self.remote_host,
                port=self.remote_port,
                record_video=self.record_video,
                http_proxy=self.http_proxy,
                session_name=self.remote_session_name,
                session_timeout=self.remote_session_timeout,
                log=self.log)
        elif self.exec_env == "seleniumbox":
            self.selenium_settings = selenium_settings.SeleniumBoxSetting(
                browser_type=self.browser_type,
                headless=self.headless,
                host=self.remote_host,
                port=self.remote_port,
                record_video=self.record_video,
                session_name=self.remote_session_name,
                token=self.remote_session_token,
                session_timeout=self.remote_session_timeout,
                log=self.log)
        else:
            raise Exception("unsupported exec_env {0}.  Currently support {1}".format(
                self.exec_env, ['local', "selenoid", "seleniumbox"]))
        self.driver = self.selenium_settings.launch_browser()
        self.session_start_time = time.time()
        self.last_coverage_capture_time = time.time()
        self._coverage_enabled = None

        if not hasattr(qali_globals, "ui"):
            qali_globals.ui = []
        qali_globals.ui.append(self)
        qali_globals.failure_message = ""
        qali_globals.memory_breach = []
        # log version information
        try:
            self.log("Python version: {0}.{1}".format(sys.version_info[0], sys.version_info[1]))
            self.log("Browser name: {0}".format(self.driver.capabilities['browserName']))
            self.log("Browser version: {0}".format(self.driver.capabilities['browserVersion']))
            if self.browser_type == "chrome":
                self.log("Driver version: {0}".format(
                    self.driver.capabilities['chrome']['chromedriverVersion']))
                # Enabling coverage generation once the session is launched
                if self.coverage_enabled:
                    self.enable_ui_function_coverage()
                    self.start_ui_function_coverage()
            if self.exec_env == "selenoid":
                self.log("Selenoid Session link : {0}".format(
                    self.selenium_settings.session_url.format(self.driver.session_id)))
                self.log_url("Selenoid Session link : {0}".format(
                    self.selenium_settings.session_url.format(self.driver.session_id)))
                if self.record_video:
                    session_host_info = self.driver.capabilities['se:cdp'].split('/')
                    self._video_url = self.selenium_settings.video_url.format(
                        session_host_info[2], session_host_info[-2])
                    url_message = self._video_url
                    if getattr(getattr(config, "runtests"), "log_viewer", False):
                        url_message = create_hyperlink(self._video_url)
                    if hasattr(api, "this_testsuite"):
                        self._add_message_to_runtests_failure_message(message_to_add=url_message)
            if self.exec_env == "seleniumbox":
                self.log_url("Seleniumbox Session link : {0}".format(
                    self.selenium_settings.session_url.format(self.driver.session_id)))
                self.runtests_log_url("Seleniumbox video link : {0}".format(
                    self.selenium_settings.video_url.format(self.driver.session_id)))
                self._video_url = self.selenium_settings.video_url.format(self.driver.session_id)
                url_message = self._video_url
                if getattr(getattr(config, "runtests"), "log_viewer", False):
                    url_message = create_hyperlink(self._video_url)
                if hasattr(api, "this_testsuite"):
                    self._add_message_to_runtests_failure_message(message_to_add=url_message)

        except Exception:
            self.log('Failed to fetch env versions')

        # check if screenshots is enabled
        enable_screenshot = os.getenv('QALI_GUI_ENABLE_SCREENSHOTS', None)
        if enable_screenshot:
            self.enable_screenshot = enable_screenshot.lower() in ['true', '1']
        else:
            self.enable_screenshot = True

        self.driver.get(self.url)

        self.timeout = getattr(getattr(config, "qali_global"), "intersight_ui_element_timeout")
        self._iframe_manager = IframeManager(self.driver)
        self._component_manager = ComponentManager(self.driver,
                                                   self.url,
                                                   self.timeout,
                                                   self._iframe_manager,
                                                   self._notification_handler,
                                                   log=self.log,
                                                   screenshot=self.screenshot)
        self._page_manager = PageManager(self)
        self.rescan()

        # version = 2 for magnetic theme , which is the default
        self.version = 2

        if sign_in:
            self.page.sign_in(
                username=username,
                password=password,
                use_sso=self.use_sso,
                idp_email=self.idp_email,
                account=self.account_name,
                role=self.account_role,
                ldap_domain=self.ldap_domain,
                create_account=create_account,
                oauth_consent_screen=oauth_consent_screen,
                region=region
            )

    def _add_message_to_runtests_failure_message(self, message_to_add: str):
        try:
            if api.this_testsuite.result.setup_timer.stop_time is None:
                api.this_testsuite.result.setup_message += message_to_add + '\n'
            elif api.this_testsuite.this_testcase.result.setup_timer.stop_time is None:
                api.this_testsuite.this_testcase.result.setup_message += message_to_add + '\n'
            elif api.this_testsuite.this_testcase.result.runtest_timer.stop_time is None:
                api.this_testsuite.this_testcase.result.msg += message_to_add + '\n'
            elif api.this_testsuite.this_testcase.result.cleanup_timer.stop_time is None:
                api.this_testsuite.this_testcase.result.cleanup_message += message_to_add + '\n'
            else:
                api.this_testsuite.result.cleanup_message += message_to_add + '\n'
        except Exception:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            self.log("".join(traceback.format_exception(exc_type, exc_value, exc_traceback)))

    def update_from_cli_data(self, cli_data: Mapping[str, Any]) -> None:
        """
            update all gui member variable base on cli data

            :param cli_data: cli data
        """
        # update account name
        self.account_name = cli_data.get("account_id_or_name", self.account_name)

        self.account_role = cli_data.get('account_role', self.account_role)

        # update use sso
        idp_domain_name = cli_data.get("idp_domain_name", None)
        if idp_domain_name:
            self.use_sso = 'cisco' in idp_domain_name.lower()

        # update chrome debug port
        self.chrome_debug_port = cli_data.get('chromeDebugPort', self.chrome_debug_port)
        if self.chrome_debug_port is not None:
            self.chrome_debug_port = str(self.chrome_debug_port)

        # update browser type
        self.browser_type = cli_data.get('browser', self.browser_type).lower()

        # update download path
        self.download_path = cli_data.get('downloadPath', self.download_path)
        self.download_path = cli_data.get('download_path', self.download_path)
        if self.download_path:
            self.download_path = self.download_path.rstrip("/")

        # update exec env
        self.exec_env = cli_data.get('execEnv', self.exec_env).lower()

        # update headless
        headless = cli_data.get("headless", None)
        if headless is not None:
            if (isinstance(headless, bool) and headless) or \
                    (isinstance(headless, str) and headless.lower() in ['true', '1']):
                self.headless = True

        # update record video.  Only applicable for remote execution
        rec_video = cli_data.get("recVideo", None)
        if rec_video is not None:
            if (isinstance(rec_video, bool) and rec_video) or \
                    (isinstance(rec_video, str) and rec_video.lower() in ['true', '1']):
                self.record_video = True

        # update driver version
        self.driver_version = cli_data.get('driver_version', self.driver_version)
        if self.driver_version:
            self.driver_version = self.driver_version.rstrip("/")

        # update remote host, check selenoidHost for backward compatibility
        self.remote_host = cli_data.get('selenoidHost', self.remote_host)
        self.remote_host = cli_data.get('remote_host', self.remote_host)

        # update remote port, check selenoidPort for backward compatibility
        self.remote_port = cli_data.get('selenoidPort', self.remote_port)
        self.remote_port = cli_data.get('remote_port', self.remote_port)

        # update remote session token
        self.remote_session_token = cli_data.get('remote_session_token', self.remote_session_token)

        # update remote session name
        self.remote_session_name = cli_data.get('remote_session_name', self.remote_session_name)

        # update remote session timeout
        self.remote_session_timeout = cli_data.get('remote_session_timeout', self.remote_session_timeout)

        # Unsupport/deprecated cli_data
        idp_email = cli_data.get("idp_email", None)
        if idp_email is not None:
            self.idp_email = idp_email
            self.use_sso = True

        role_name = cli_data.get("roleName", None)
        if role_name is not None:
            self.log("!!!!! Warning: roleName cli_data is not supported. !!!!!")

        org = cli_data.get("org", None)
        if org is not None:
            self.log("!!!!! Warning: org cli_data is not supported. !!!!!")

        platform_type = cli_data.get("platformType", None)
        if platform_type is not None:
            self.log("!!!!! Warning: platformType cli_data is not supported. !!!!!")

        imc_ip = cli_data.get("imcIp", None)
        if imc_ip is not None:
            self.log("!!!!! Warning: imcIp cli_data is not supported. !!!!!")

        enable_version_logging = cli_data.get("enableVersionLogging", None)
        if enable_version_logging is not None:
            # version will always get logged
            self.log("!!!!! Warning: enableVersionLogging cli_data is not supported. !!!!!")

    def log_level(self, level: int = logging.INFO) -> None:
        """
            set log level.  if level is not given, debug level will be used.

            :param level: desired log level

            :return: None
        """
        self._log_level = level

    def click_ctx(self,
                  context: str,
                  path_context: Optional[Union[str, Tuple[str, ...]]] = None,
                  timeout: Optional[int] = None) -> ClickManager:
        """
            return click context manager with given context and path_context.

            Interaction with the context can be performed via method of click context manager

            :param context: context of click context
            :param path_context: path context of click context
            :param timeout: time to wait for context to be ready.

            :return: click manager with given context
        """

        if timeout is None:
            timeout = self.timeout
        return ClickManager(context,
                            path_context,
                            timeout,
                            component_manager=self._component_manager,
                            iframe_manager=self._iframe_manager,
                            log=self.log,
                            screenshot=self.screenshot,
                            page_errors=self.page_errors)

    def input_ctx(self,
                  context: str,
                  path_context: Optional[Union[str, Tuple[str, ...]]] = None,
                  timeout: Optional[int] = None) -> InputManager:
        """
            return input context manager with given context and path_context.

            Interaction with the context can be performed via method of input context manager

            :param context: context of input context
            :param path_context: path context of input context
            :param timeout: time to wait for context to be ready.

            :return: input manager with given context
        """
        if timeout is None:
            timeout = self.timeout
        return InputManager(context,
                            path_context,
                            timeout,
                            component_manager=self._component_manager,
                            iframe_manager=self._iframe_manager,
                            log=self.log,
                            screenshot=self.screenshot,
                            page_errors=self.page_errors)

    def select_ctx(self,
                   context: str,
                   path_context: Optional[Union[str, Tuple[str, ...]]] = None,
                   timeout: Optional[int] = None) -> SelectManager:
        """
            return select context manager with given context and path_context.

            Interaction with the context can be performed via method of select context manager

            :param context: context of select context
            :param path_context: path context of select context
            :param timeout: time to wait for context to be ready.

            :return: select manager with given context
        """
        if timeout is None:
            timeout = self.timeout
        return SelectManager(context,
                             path_context,
                             timeout,
                             component_manager=self._component_manager,
                             iframe_manager=self._iframe_manager,
                             log=self.log,
                             screenshot=self.screenshot,
                             page_errors=self.page_errors)

    def table_ctx(self,
                  context: str = None,
                  path_context: Optional[Union[str, Tuple[str, ...]]] = None,
                  timeout: Optional[int] = None) -> TableManager:
        """
            return table context manager with given context and path_context.

            Interaction with the context can be performed via method of table context manager

            :param context: context of table context
            :param path_context: path context of table context
            :param timeout: time to wait for context to be ready.

            :return: table manager with given context
        """
        if timeout is None:
            timeout = self.timeout
        return TableManager(context,
                            path_context,
                            timeout,
                            component_manager=self._component_manager,
                            iframe_manager=self._iframe_manager,
                            log=self.log,
                            screenshot=self.screenshot,
                            page_errors=self.page_errors)

    def canvas_ctx(self,
                   context: str = None,
                   path_context: Optional[Union[str, Tuple[str, ...]]] = None,
                   timeout: Optional[int] = None) -> CanvasManager:
        """
            return canvas context manager with given context and path_context.

            Interaction with the context can be performed via method of canvas context manager

            :param context: context of canvas context
            :param path_context: path context of canvas context
            :param timeout: time to wait for context to be ready.

            :return: canvas manager with given context
        """
        if timeout is None:
            timeout = self.timeout
        return CanvasManager(context,
                             path_context,
                             timeout,
                             component_manager=self._component_manager,
                             iframe_manager=self._iframe_manager,
                             log=self.log,
                             screenshot=self.screenshot,
                             page_errors=self.page_errors)

    def data_ctx(self,
                 context: str,
                 path_context: Optional[Union[str, Tuple[str, ...]]] = None,
                 timeout: Optional[int] = None) -> DataManager:
        """
            return data context manager with given context and path_context.

            Interaction with the context can be performed via method of data context manager

            :param context: context of data context
            :param path_context: path context of data context
            :param timeout: time to wait for context to be ready.

            :return: data manager with given context
        """
        if timeout is None:
            timeout = self.timeout
        return DataManager(context,
                           path_context,
                           timeout,
                           component_manager=self._component_manager,
                           iframe_manager=self._iframe_manager,
                           log=self.log,
                           screenshot=self.screenshot,
                           page_errors=self.page_errors)

    def notification_ctx(self,
                         context: str = None,
                         path_context: Optional[Union[str, Tuple[str, ...]]] = None,
                         timeout: Optional[int] = None) -> NotificationManager:
        """
            return notification context manager with given context and path_context.

            Interaction with the context can be performed via method of notification context manager

            :param context: context of notification context
            :param path_context: path context of notification context
            :param timeout: time to wait for context to be ready.

            :return: notification manager with given context
        """
        if timeout is None:
            timeout = self.timeout
        return NotificationManager(context,
                                   path_context,
                                   timeout,
                                   component_manager=self._component_manager,
                                   iframe_manager=self._iframe_manager,
                                   log=self.log,
                                   screenshot=self.screenshot,
                                   page_errors=self.page_errors)

    def error_ctx(self,
                  context: str,
                  path_context: Optional[Union[str, Tuple[str, ...]]] = None,
                  timeout: Optional[int] = None) -> ErrorManager:
        """
            return error context manager with given context and path_context.

            Interaction with the context can be performed via method of error context manager

            :param context: context of error context
            :param path_context: path context of error context
            :param timeout: time to wait for context to be ready.

            :return: error manager with given context
        """
        if timeout is None:
            timeout = self.timeout
        return ErrorManager(context,
                            path_context,
                            timeout,
                            component_manager=self._component_manager,
                            iframe_manager=self._iframe_manager,
                            log=self.log,
                            screenshot=self.screenshot,
                            page_errors=self.page_errors)

    def _get_video_time(self):
        """
            This helper method facilitates the conversion of timestamp differences in seconds into a more readable
            format. This allows for easy interpretation of the time taken for specific steps in recordings

            :param : None
            :return: A string representing time in a clear and readable format
        """
        current_video_time = time.time() - self.session_start_time
        minutes, seconds = divmod(current_video_time, 60)
        if minutes > 60:
            hours, minutes = divmod(minutes, 60)
            video_time = f"{int(hours):02d}:{int(minutes):02d}:{seconds:02.0f}"
        else:
            video_time = f"{int(minutes):02d}:{seconds:02.0f}"
        return video_time

    def log(self, msg: Optional[str] = None, log_level=logging.INFO) -> bool:
        """
            This is a logger method, we can use it if we want to log some message in the output

            :param msg: message to be logged.  If None, no message will be logged and can be used to
                        determine logging is required or not
            :param log_level: log level of the message
            :return: Whether message is logged with given log level
        """
        if log_level >= self._log_level:
            if msg is not None:
                try:
                    if log_level <= logging.DEBUG:
                        self._spyfile.write("DEBUG - " + msg + '\n')
                    else:
                        if self.record_video and VALID_STRING_REGEX.search(msg):
                            link_name = "[ Video Time: " + self._get_video_time() + " ] "
                            msg = self._video_url + "#t=" + self._get_video_time() + " " + msg
                            self._spyfile.hyperlink_write(message=msg + '\n', link_name=link_name)
                        else:
                            self._spyfile.write(msg + '\n')

                except Exception:
                    pass

            return True
        return False

    def log_url(self, msg: Optional[str] = None, log_level=logging.INFO, link_name: Optional[str] = None) -> bool:
        """
            This is a logger method, we can use it if we want to log some message in the output

            :param msg: message to be logged.  If None, no message will be logged and can be used to
                        determine logging is required or not
            :param log_level: log level of the message
            :return: Whether message is logged with given log level
        """
        if log_level >= self._log_level:
            if msg is not None:
                try:
                    self._spyfile.hyperlink_write(msg + '\n', link_name=link_name, log_level=log_level)
                except Exception:
                    pass

            return True
        return False

    def runtests_log(self, msg: Optional[str] = None):
        """
            This is a logger method which log as non spy output in runtests logger.  If
            runtests is not used, log with log method instead.

            :param msg: message to be logged.  If None, no message will be logged and can be used to
                        determine logging is required or not
            :return: None
        """
        try:
            api["runtests_logger"].info(msg)
        except Exception:
            # no runtests_logger defined, use regular logger instead
            self.log(msg)

    def runtests_log_url(self, msg: Optional[str] = None, link_name: Optional[str] = None):
        """
            This is a logger method which log as non spy output in runtests logger.  If
            runtests is not used, log with log method instead.

            :param msg: message to be logged.  If None, no message will be logged and can be used to
                        determine logging is required or not
            :return: None
        """
        try:
            api["runtests_logger"].hyperlink_info(msg, link_name=link_name)
        except Exception:
            # no runtests_logger defined, use regular logger instead
            self.log_url(msg, link_name=link_name)

    @property
    def page(self) -> PageManager:
        """
            return page manager which will automatically create page access base on current url

            corresponding method then can be call to perform the operation.

            :return: page manager
        """
        return self._page_manager

    @property
    def current_url(self) -> str:
        """
            return current url of GUI session

            :return: current url of GUI session
        """
        return self.driver.current_url

    def url_match(self, url: Union[str, RePattern]) -> UrlMatchContext:
        """
            return current url of GUI session

            :return: current url of GUI session
        """
        return UrlMatchContext(self.driver, url)

    def wait_ctxs(self,
                  contexts: List[Union[ContextManager, UrlMatchContext, Callable]],
                  timeout: Optional[int] = None,
                  interval: Optional[int] = None,
                  exc: Optional[bool] = False) -> Optional[int]:
        """
            wait for one of given contexts until timeout.  Return first index matched.

            for example:

            The following will wait for "abc" click context, "myinput" input context, or
            session url with "http://myurl"

            ui.wait_ctxs([ui.click_ctx("abc"), ui.input_ctx("myinput"), ui.url_match("http://myurl")])

            If click found first, 0 is returned
            If input found first, 1 is returned
            If url found first, 2 is returned

            :param contexts: list of contexts to wait
            :param timeout: time to wait for matching one of the given contexts.
            :param interval: interval to wait before retry.
            :param exc: whether or not to raise an exception if none of the contexts are found.
            :return: return matched index.  If not matched within time interval, return None
        """

        if not isinstance(contexts, list):
            raise Exception("wait_ctxs contexts parameter must be a list (you gave {0})".format(type(contexts)))
        if timeout is None:
            timeout = self.timeout

        if interval:
            wait_time_gen = util.wait_time.generator(interval,
                                                     interval,
                                                     timeout)
        else:
            wait_time_gen = util.wait_time.generator(Context.START_WAIT_TIME,
                                                     Context.MAX_INTERVAL_TIME,
                                                     timeout)
        stop = False
        start_time = time.monotonic()
        begin_time = start_time
        while not stop:
            try:
                for index, ctx in enumerate(contexts):
                    if hasattr(ctx, "exist"):
                        func = ctx.exist
                    elif callable(ctx):
                        func = ctx
                    else:
                        raise Exception("Context {0} either need to have exist function or be callable".format(ctx))
                    if func():
                        total_time = round(time.monotonic() - start_time, 3)
                        self.log("Found context with index {0} after {1} seconds.".format(index, total_time))
                        return index
            except (exceptions.StaleElementReferenceException,
                    exceptions.NoSuchElementException):
                pass
            except exceptions.WebDriverException as err:
                error_message = str(err)
                if "502 Bad Gateway" in error_message:
                    pass
                else:
                    raise err

            util.wait_time.time_took = time.monotonic() - start_time
            try:
                wait_time = next(wait_time_gen)
                time.sleep(wait_time)
            except StopIteration:
                stop = True
            start_time = time.monotonic()
            self.rescan()
        contexts_str = []
        for ctx in contexts:
            if hasattr(ctx, "repr"):
                contexts_str.append(ctx.repr())
            elif inspect.ismethod(ctx):
                # Get the class of the method
                method_class_obj = ctx.__self__

                if hasattr(method_class_obj, "repr"):
                    contexts_str.append(method_class_obj.repr() + '.' + ctx.__name__)
            elif inspect.isfunction(ctx):

                contexts_str.append(ctx.__name__)
        self.log("None of the following requested context found", log_level=logging.ERROR)
        self.log('\n'.join(contexts_str), log_level=logging.ERROR)
        if exc:
            total_time = int(time.monotonic() - begin_time)
            self.screenshot("Contexts Not Found")
            raise Exception("None of the expected contexts were found after {0} seconds\n"
                            " contexts requested-\n{1}".format(total_time, '\n'.join(contexts_str)))
        return None

    def rescan(self) -> None:
        """
            rescan GUI session page.

            :return: None
        """
        if self.coverage_enabled:
            self.capture_ui_function_coverage(store_coverage_data=True)
        self._component_manager.rescan_page()

    def refresh(self) -> None:
        """
            refresh GUI web page.

            :return: None
        """
        self.driver.refresh()

    def _notification_handler(self, notification_context: NotificationContextMap) -> None:
        """
            Internal notification handler which register as callback in component manager.
            The callback will be made by component manager on every page rescan.
            If auto close notification flag is set to True,
            The notification handler will auto close any default/success notification, and
            stored closed notification in self.auto_closed_notifications

            :param notification_context: notification context for current rescan

            :return: None


        """

        if self.auto_close_notification:
            closed_notification = self.notification_ctx("default").close_all(rescan=False)
            closed_notification.extend(self.notification_ctx("success").close_all(rescan=False))
            closed_notification.extend(self.notification_ctx("tooltip").close_all(rescan=False))
            closed_notification.extend(self.notification_ctx("info").close_all(rescan=False))
            self.auto_closed_notifications.extend(closed_notification)
            self.auto_closed_notifications = self.auto_closed_notifications[-100:]

        if self.log_err_notification:
            seen_notifications = set()
            existing_notification_keys = {(type, message) for type, message, _, _ in self.err_notifications}

            # Collect current valid alert notifications
            for msg_type, msg_map in self._component_manager.notification_context.items():
                if msg_type not in ['alert', 'error']:
                    continue
                for msg, context in msg_map.items():
                    key = (msg_type, msg)
                    if key not in seen_notifications:
                        seen_notifications.add(key)
                        # Only add if not already present in err_notifications
                        if key not in existing_notification_keys:
                            try:
                                notification_details = context.details(timeout=1)
                            except Exception:
                                notification_details = {}
                            notification_log = self.screenshot(video_link=True)
                            self.err_notifications.append((msg_type, msg, notification_log, notification_details))

            # Remove stale alerts (not in current seen notifications)
            self.err_notifications = [
                (msg_type, msg, notification_msg, details)
                for (msg_type, msg, notification_msg, details) in self.err_notifications
                if (msg_type, msg) in seen_notifications
            ]

    def get_auto_close_notifications(self, rescan: bool = True) -> List[Tuple[str, str]]:
        """
            return all notifications that are auto closed

            :return: all notifications that are auto closed
        """
        # return a copy of notification
        if rescan:
            self.rescan()
        return self.auto_closed_notifications[:]

    def get_error_notifications(self) -> List[Tuple[str, str]]:
        """
            return all error notification in current page.

            :return: all notifications that are auto closed
        """
        return self.notification_ctx("alert").get_notifications()

    def clear_auto_close_notifications(self, rescan: bool = True) -> List[Tuple[str, str]]:
        """
            clear all auto closed notification stored and return the copy
            of it back

            :return: all notifications that are auto closed
        """
        if rescan:
            self.rescan()
        temp_list = self.auto_closed_notifications
        self.auto_closed_notifications = []
        return temp_list

    def is_onprem(self) -> bool:
        """
            return True if current UI session is onprem appliance

            :return: True if current UI session is onprem appliance
        """
        for cloud_host in CLOUD_HOSTS:
            if cloud_host in self.url:
                return False
        return True

    def get_ctxs(self,
                 rescan: bool = True,
                 context: str = None) -> Mapping[str, Mapping[str, Mapping[Union[str, Tuple[str, ...]], Context]]]:
        """
            get all available context in the current url page

            :param rescan: If True, rescan the url page.  Otherwise skip rescan
            :param context: specific context to return
            :return: all available context in the current page.
        """
        rtr_map = {}
        error = None
        for _ in range(2):
            try:
                if rescan:
                    self._component_manager.rescan_page()

                if context is None:
                    rtr_map["click"] = self._component_manager.click_context
                    rtr_map["select"] = self._component_manager.select_context
                    rtr_map["input"] = self._component_manager.input_context
                    rtr_map["table"] = self._component_manager.table_context
                    rtr_map["canvas"] = self._component_manager.canvas_context
                    rtr_map["data"] = self._component_manager.data_context
                    rtr_map["notification"] = self._component_manager.notification_context
                    rtr_map["error"] = self._component_manager.error_context
                elif context == "click":
                    rtr_map["click"] = self._component_manager.click_context
                elif context == "select":
                    rtr_map["select"] = self._component_manager.select_context
                elif context == "input":
                    rtr_map["input"] = self._component_manager.input_context
                elif context == "table":
                    rtr_map["table"] = self._component_manager.table_context
                elif context == "canvas":
                    rtr_map["canvas"] = self._component_manager.canvas_context
                elif context == "data":
                    rtr_map["data"] = self._component_manager.data_context
                elif context == "notification":
                    rtr_map["notification"] = self._component_manager.notification_context
                elif context == "error":
                    rtr_map["error"] = self._component_manager.error_context
                else:
                    raise Exception(f"Undefined context {context}")
                break
            except Exception as err:
                error = err
        else:
            raise error
        return rtr_map

    def print_ctxs(self,
                   rescan: bool = True,
                   context: str = None) -> None:
        """
            print all available context in the current url page
            :param rescan: If True, rescan the url page.  Otherwise skip rescan
            :param context: specific context to print
            :return: None
        """
        pprint.pprint(self.get_ctxs(rescan, context))

    def get_contexts_with_label(self, label: Any, rescan: bool = True, ignore: Optional[List[str]] = None):
        """
            Gets a list of context types that contain a context with the given label

            :param label: The label to search for
            :param rescan: If True, rescan the url page.  Otherwise skip rescan
            :param ignore: An optional list of contexts to ignore
            :returns: A list of context types that contain a context with the given label
        """
        if ignore is None:
            ignore = ["error"]
        matching_contexts = []
        for context_type, contexts in self.get_ctxs(rescan).items():
            if label in contexts and (not ignore or context_type not in ignore):
                matching_contexts.append(context_type)
        return matching_contexts

    def screenshot(self,
                   msg: Optional[str] = None,
                   video_link: Optional[bool] = False) -> str:
        """
            Method that takes screenshot and saves in the log directory with name msg

            :param msg: msg append to the path

            :return: screenshot path
        """
        screenshot_path = ''
        try:
            if self.enable_screenshot:
                if msg is not None:
                    msg = msg.replace(" ", "_")
                screenshot_name = '{0}_{1}.png'.format(datetime.datetime.now().strftime("%Y%m%d%H%M%S"), msg)
                path = self.screenshot_path if self.screenshot_path else log_dir()
                screenshot_path = os.path.join(path, screenshot_name)
                self.driver.save_screenshot(screenshot_path)
                # replace name with http path if possible
                try:
                    http_root = api['this_testsuite'].root.url_prefix
                    output_root = api['this_testsuite'].root.runtests_root
                except Exception:
                    http_root = getattr(getattr(config, "qali_global"), "http_root")
                    output_root = getattr(getattr(config, "qali_global"), "local_root")
                if http_root and output_root:
                    screenshot_path = screenshot_path.replace(output_root, http_root)
                if self.record_video:
                    self.video_instance = self._video_url + "#t=" + self._get_video_time()
                    self.log_url("Video link for below screenshot : " + self.video_instance)
                    if getattr(getattr(config, "runtests"), "log_viewer", False):
                        msg_url = "Failure at : " + create_hyperlink(self.video_instance)
                    else:
                        msg_url = "Failure at : " + self.video_instance
                    if not video_link:  # to avoid duplication of failure msg
                        qali_globals.failure_message = msg_url

                self.log("Screenshot at {0}".format(screenshot_path))
                if video_link and self.record_video:
                    # if video link is requested, return video link
                    return msg_url
                # rp_name = msg if msg else "screenshot_"  str(report_portal.timestamp())
                # if hasattr(report_portal, "service"):
                # with open(screenshot_path, "rb") as fh:
                #    screen_shot_data = fh.read()

                # attachment = {"name": rp_name + ".png",
                #              "data": screen_shot_data,
                #              "mime": "application/octet-stream"}
                # report_portal.service.log(report_portal.timestamp(), rp_name, "INFO", attachment=attachment)
            else:
                self.log("Screenshots disabled. Skip screenshot for '{0}'".format(msg))
        except Exception as message:
            self.log("!!!!! Screenshot capture failed with error: {0} !!!!!".format(message))
        return screenshot_path

    def assert_func(
            self,
            condition: bool,
            error_message: Optional[str] = None,
            capture_screenshot: Optional[bool] = True):
        """
            This method mimics the behavior of the built-in assert keyword in Python.
            Additionally captures a screenshot of the user interface in the event of a failure.
            raises AssertionError: If the condition is False.

            :param condition: The condition to be tested.
            :param error_message: The error message to be displayed when the condition is False.
            :param capture_screenshot: If set to True, will capture screenshot at time of Asser Failure. Default True

            returns: None 
        """
        if not condition:
            if capture_screenshot:
                self.screenshot("Assert Failed here")
            raise AssertionError(error_message)

    def get_clipboard_data(self) -> str:
        """
            Method to return the data present in the clipboard

            :return: data in the clipboard
        """
        return self.selenium_settings.get_clipboard_data(self.driver)

    def get_file_download_link(self) -> str:
        """
            Method to return the file download link

            :return: url for file
        """
        return self.selenium_settings.get_download_url(self.driver)

    def switch_to_window(self, title: str, timeout: int = 10) -> None:
        """
            Method to switch to window with given title

            :param title: the title of the window to switch to
            :param timeout: maximum number of seconds to wait for the window with the given title
            :return: None
        """
        start_time = time.time()
        while True:
            try:
                window_handles = self.driver.window_handles
                titles = []
                initial_window_handle = None
                matching_window_handles = []
                for window_handle in window_handles:
                    if initial_window_handle is None:
                        initial_window_handle = window_handle
                    self.driver.switch_to.window(window_handle)
                    window_title = self.driver.title
                    titles.append(window_title)
                    if title in window_title:
                        matching_window_handles.append(window_handle)
                num_matches = len(matching_window_handles)
                if num_matches == 0:
                    self.driver.switch_to.window(initial_window_handle)
                    raise Exception(f"No window title found containing '{title}' in {titles}")
                if num_matches > 1:
                    self.driver.switch_to.window(initial_window_handle)
                    raise Exception(f"More than one window title found containing '{title}' in {titles}")
                self.driver.switch_to.window(matching_window_handles[0])
                self.log(f"Switched to window with title '{self.driver.title}'")
                break
            except Exception as exc:
                if int(time.time() - start_time) > timeout:
                    raise exc
                time.sleep(1)

    def quit(self) -> None:
        """
            quit web session

            :return: None
        """
        if self.driver is not None:
            try:
                if self.coverage_enabled:
                    self.capture_ui_function_coverage(store_coverage_data=True)
                self.page.sign_out()
            except Exception as exc:
                self.log(f"Failed to sign out: {exc}")
            self.driver.quit()
            self.driver = None
            qali_globals.ui.remove(self)

    def back(self, url: str = None) -> None:
        """
            go back to previous url.

            :param url: url to move back.
            :return: None
        """
        self.driver.back()
        if url:
            for _ in range(10):
                # try maximum 10 times
                if self.driver.current_url == url:
                    break
                self.driver.back()

    def get_cookie(self, cookie_name: str = 'X-Starship-Token') -> str:
        """
            return the cookie value as per the name passed
            Usage: handle.get_cookie(cookieName)

            :param cookie_name: cookie name
            :return: return cookie value of the session.
        """
        return self.driver.get_cookie(cookie_name)['value']

    def run_accessibility_tests(self) -> List[Mapping[str, Any]]:
        """
            return Axe accessibility tests result.

            https://github.com/dequelabs/axe-core/blob/master/doc/API.md

            :return: list of violation found by axe accessibility tests
        """
        axe = Axe(self.driver)
        axe.inject()
        results = axe.run(options=self.accessibility_options)
        return results['violations']

    def page_errors(self, text: bool = False) -> Union[str, List[Mapping[str, str]]]:
        """
        Method to get list of errors in a page

        :return: list of errors in format
            {'Error Context': <error_context_name>, 'Path Context': <path_context>, 'Error Message': <Error_Message>}
        """
        error_list = []
        for context_label, context in self.get_ctxs(rescan=True)['error'].items():
            for path_context in context.keys():
                error_list.append(
                    {'Error Context': context_label,
                     'Path Context': path_context,
                     'Error Message': self.error_ctx(context_label, path_context=path_context).text()})
        if text:
            error_string = ''
            if error_list:
                error_string = "\n" + "-" * 150 + "\n"
                for errors in error_list:
                    error_string += f"Error in Context '{errors['Error Context']}'" \
                        f" with message: {errors['Error Message']}\n"
                error_string += "-" * 150
            return error_string
        return error_list

    def get_unhandled_error_notifications(self) -> List[Tuple[str, str, str, Any]]:
        """
            Method to get unhandled error notifications from the page

            :return: List of unhandled error notifications
        """
        self.rescan()
        err_notifications_snapshot = copy.deepcopy(self.err_notifications)
        self.notification_ctx("alert").close_all()
        self.notification_ctx("error").close_all()
        return err_notifications_snapshot

    def get_session_memory_stats(self) -> Mapping[str, int]:
        """
            Method to get the memory stats for the session
        """
        memory = self.driver.execute_script("return performance.memory")
        return memory

    def console_log(self, log_type='browser') -> Mapping[str, str]:
        """
            Method to extract the browser console logs

            :returns: List of dictionary of browser logs,
            Dictionary of Count of Broswer Severity
        """
        if self.browser_type.capitalize() in 'Chrome':
            browser_severity_count = {}
            logs = self.driver.get_log('browser')
            for log in logs:
                log['timestamp'] = datetime.datetime.fromtimestamp(
                    log['timestamp'] / 1000).strftime("%Y-%m-%d %H:%M:%S")
                browser_severity_count[log['level']] = browser_severity_count.get(
                    log['level'], 0) + 1
            return logs, browser_severity_count
        return "Not supported for {0} browser".format(self.browser_type)

    def capture_network_logs(self) -> List:
        """
        Captures and returns network performance data as a list of dictionaries.

        :return: List of dictionaries containing network log data,
        """
        if self.browser_type.capitalize() in 'Chrome':
            # Get Network logs
            logs = self.driver.get_log("performance")
            network_logs = []

            for log in logs:
                network_log = json.loads(log["message"])["message"]

                # Check if the log entry is network-related
                if "Network.response" in network_log["method"] or \
                    "Network.request" in network_log["method"] or \
                        "Network.webSocket" in network_log["method"]:
                    if 'timestamp' in network_log['params'].keys():
                        network_log['params']['timestamp'] = datetime.datetime.fromtimestamp(
                            network_log['params']['timestamp'] / 1000).strftime("%Y-%m-%d %H:%M:%S")
                    network_logs.append(network_log)

            return network_logs
        return "Not supported for {0} browser".format(self.browser_type)

    def _execute_command(self, cmd: str, params: dict = None) -> Dict:
        """
            Helper method to execute CDP commands.
            :param cmd: Command to execute
            :param params: Parameters for the command
            :return: Result of the command execution
        """
        if params is None:
            params = {}
        return self.driver.execute(
            driver_command="executeCdpCommand",
            params={"cmd": cmd, "params": params}
        )

    def enable_ui_function_coverage(self) -> None:
        """
            Enables the function coverage.
            :return: None
        """
        self._execute_command("Profiler.enable")

    def start_ui_function_coverage(self) -> None:
        """
            Starts capturing coverage from this point.
            :return: None
        """
        # Capturing Coverage from this time
        self.last_coverage_capture_time = time.time()
        self._execute_command("Profiler.startPreciseCoverage", {"detailed": True})

    def capture_ui_function_coverage(self, store_coverage_data: bool = True, check_threshold=False) -> Dict:
        """
            Capture UI function coverage data using the Chrome DevTools Protocol `Profiler.takePreciseCoverage`.
            This method captures UI coverage and, if `store_coverage_data` is enabled, stores the raw coverage
            output as a JSON file in the current test's log directory. The file name format is:
            `raw_coverage_<timestamp>.json`.
            If no test is currently running and coverage capture is triggered due to a threshold timeout
            (e.g., long suite setup), the coverage data is captured but not stored.
            :param store_coverage_data:  Whether to store the captured coverage data to a JSON file. Defaults 
                to "True".
            :param check_threshold: If `True`, enforces a minimum time interval (`self.coverage_capture_threshold`) 
                between consecutive captures. If the threshold is not met, the method exits early.
                Defaults to `False`.

            `raw_coverage_{timestamp}.json`. If no test is running, Just empties the buffer
            :return: None
        """
        if check_threshold:
            if time.time() - self.last_coverage_capture_time < self.coverage_capture_threshold:
                return

        self.last_coverage_capture_time = time.time()
        if store_coverage_data:
            test_case = getattr(api['this_testsuite'], "this_testcase", None)
            if not test_case:
                # When called because the capture threshold is reached like suite setup taking more then 10 minutes
                self._execute_command("Profiler.takePreciseCoverage")
                return
            output_dir = test_case.get_output_dir()
            current_timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
            raw_coverage_file_path = os.path.join(output_dir, f"raw_coverage_{current_timestamp}.json")
            data = self._execute_command("Profiler.takePreciseCoverage")
            with open(raw_coverage_file_path, "w", encoding="utf-8") as file:
                json.dump(data, file, indent=4)
        else:
            self._execute_command("Profiler.takePreciseCoverage")

    def disable_capturing_coverage(self) -> None:
        """
            Stops capturing coverage and disables the profiler.
            :return: None
        """
        self._execute_command("Profiler.stopPreciseCoverage")
        self._execute_command("Profiler.disable")

    @property
    def coverage_enabled(self) -> bool:
        """
            Property to return coverage is enabled or not
        """
        try:
            if self._coverage_enabled is None:
                app_options = get_app_options_instance()
                plugins_enabled = set(set(app_options.options.enabled_plugins) -
                                      set(app_options.options.disabled_plugins))
                if 'ui_coverage' in plugins_enabled:
                    self._coverage_enabled = True
                else:
                    self._coverage_enabled = False
        except Exception as err:
            self.log(f"Please check the cli parameters. There could be duplicate params. {err}")
            self._coverage_enabled = False
        return self._coverage_enabled

    def get_downloaded_json_file_url(self, filename: str) -> str:
        """
        Get the direct URL of the downloaded JSON file (seleniumbox environment only).

        :param filename: Base name of the file (without .json)
        :return: Direct URL to the file
        """
        if self.exec_env != 'seleniumbox':
            raise Exception(
                f"This method is only applicable for 'seleniumbox' execution environment, not '{self.exec_env}'")

        try:
            downloadLink = self.get_file_download_link()
            self.log(f'DownloadLink is :  {downloadLink}')

            resp = requests.get(downloadLink, timeout=10)
            if not resp.status_code == 200:
                raise Exception(f'Failed to fetch file list: {resp.status_code}')

            jsonFileContents = json.loads(resp.content)
            target_filename = filename + '.json'

            for entry in jsonFileContents:
                if entry.get('name') == target_filename:
                    return 'http://' + entry.get('executor') + ':8080' + entry.get('url')

        except Exception as error:
            raise Exception(f'JSON file not found in the download list due to error: {error}')


def log_dir() -> str:
    """
        This method will find log directory from spyfile.
        if there is no such directory it will create the directory.

        If spyfile has no logger, then /tmp is used.

        :return log directory path
    """
    if hasattr(api, "current_log_filepath"):
        path = re.sub('log$', 'screenshots', str(api.current_log_filepath))
    else:
        path = '/tmp/screenshots'

    if not os.path.exists(path):
        os.makedirs(path)
        os.system('chmod -R 777 {0}'.format(path))
    return path
