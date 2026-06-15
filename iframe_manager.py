"""
iframe manager definitions
"""
import time
from typing import List
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.common.exceptions import InvalidSessionIdException
from selenium.common.exceptions import WebDriverException
from selenium.common.exceptions import NoSuchWindowException


class IframeManager:
    """
        iframe manager class definition.  

        The purpose of this is to keep track of web driver current iframe location.
        So when context needs to be access in particular frame, we can simply set desire iframe
        and iframe manager will be responsible to switch over to given iframe.
    """

    def __init__(self, driver: WebDriver) -> None:
        """
            init function of iframe manager

            :param driver: selenium web driver
            :return: None        
        """
        self.driver = driver
        self._curr_iframes = None

    @property
    def iframes(self) -> WebElement:
        """
            return current iframe

            :return: current iframe
        """
        return self._curr_iframes

    @iframes.setter
    def iframes(self, new_iframes: List[WebElement]) -> None:
        """
            set desire iframe for the web driver

            :return: None
        """

        if new_iframes != self._curr_iframes:
            if len(new_iframes) == 0:
                self._switch_to_default_frame()
            else:
                if len(self._curr_iframes):
                    # switch to default first, since we are not in default frame
                    self._switch_to_default_frame()
                for new_frame in new_iframes:
                    self.driver.switch_to.frame(new_frame)
            self._curr_iframes = new_iframes

    def _switch_to_default_frame(self) -> None:
        """
            switch to default frame
            :return: None
        """
        error = None
        for _ in range(5):
            try:
                self.driver.switch_to.default_content()
                break
            except (InvalidSessionIdException, WebDriverException, NoSuchWindowException) as err:
                # some time when running in selenoid mode, firefox fail to switch
                # iframe to default, so simply retry again
                time.sleep(1)
                error = err
        else:
            raise error
