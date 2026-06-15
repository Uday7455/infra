"""
Intersight GUI model util definitions
"""
import logging
import re

# pylint: disable=too-many-nested-blocks,protected-access,too-many-branches,raise-missing-from, broad-exception-raised
import time
from collections import OrderedDict
from dataclasses import dataclass, is_dataclass
from functools import wraps
from typing import TYPE_CHECKING, Any, Callable, Generator, List, Mapping, Optional, Tuple, Union

from selenium.common import exceptions as selenium_exceptions
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.ui import WebDriverWait

from qali import globals as qali_globals
from qali.intersight.gui import util
from qali.intersight.gui.exceptions import ContextNotFound, PageError, ReturnErrorMsg, ValueNotFound, ValueNotSet
from qali.intersight.gui.label_remap import mapper

if TYPE_CHECKING:
    from qali.intersight.gui.component_manager import ComponentManager  # @UnusedImport
    from qali.intersight.gui.iframe_manager import IframeManager  # @UnusedImport

EXTERNAL_REPLACE_KEY = "<hex>"


class FifoCache(OrderedDict):
    """
    https://stackoverflow.com/questions/2437617/how-to-limit-the-size-of-a-dictionary
    """

    def __init__(self, *args, **kwds):
        self.size_limit = kwds.pop("size_limit", 3)
        OrderedDict.__init__(self, *args, **kwds)
        self._check_size_limit()

    def __setitem__(self, key, value):
        OrderedDict.__setitem__(self, key, value)
        self._check_size_limit()

    def _check_size_limit(self):
        if self.size_limit is not None:
            while len(self) > self.size_limit:
                self.popitem(last=False)

    def clear_cache(self):
        """
            Clears the Cache
        """
        self.clear()


class CommonInfo:
    """
        Common Info class definition
        This is stored common information that shared across
        web components and context
    """

    def __init__(self,
                 url: str,
                 component_manager: "ComponentManager",
                 iframes: List[WebElement],
                 log: Callable) -> None:
        """
            Constructor of CommonInfo

            :param url: current url
            :param iframe: current iframe web element
            :param log: logging handler

            :return: None

        """
        self.url = url
        self.component_manager = component_manager
        self.iframes = iframes
        self.log = log
        self._parsed_url = None

    @property
    def parsed_url(self) -> str:
        """
            return processed Intersight url.  Currently it will replace "-" with "_" and <moid> with replaced_moid.

            :return: processed Intersight url
        """
        if self._parsed_url is None:
            self._parsed_url = util.process_url(self.url)

        return self._parsed_url


class Context:
    """
        Base class for Context class definitions
    """

    CONTEXT_WAIT_TIME = 2
    START_WAIT_TIME = 0.01
    MAX_INTERVAL_TIME = 2

    def __init__(self,
                 element: WebElement,
                 element_func: Callable = None,
                 common_info: CommonInfo = None):
        """
            constructor of context base class

            :param element: web element for the context
            :param element_func: element callback to get actual element for interaction
            :param common_info:  common information shared to the context

            :return None
        """
        self.element = element
        self.driver = element.parent
        self.element_func = element_func

        self._actual_element = None
        self.common_info = common_info

    def highlight(self) -> None:
        """
            highlight context on the browser
            :return: None
        """
        util.highlight(self.driver, self.highlight_element)

    def clear_highlight(self) -> None:
        """
            clear all highlighted from the browser
            :return: None
        """
        util.clear_highlight(self.driver)

    @property
    def highlight_element(self) -> WebElement:
        """
            return element used to be highlight for context
        :return: element used to be highlight
        """
        return self.actual_element

    @property
    def actual_element(self) -> WebElement:
        """
            return actual web element for interaction.

            :return: web element for interaction.
        """
        if self._actual_element is None:
            if self.element_func:
                self._actual_element = self.element_func(self.element)
            else:
                self._actual_element = self.element

        return self._actual_element

    def click_element(self,
                      element: WebElement,
                      timeout: int) -> None:
        """
            click on given web element

            :param element: web element to click
            :param timeout: time to wait for web element.
            :return: None
        """

        # WebDriverWait(self.driver, self.CONTEXT_WAIT_TIME).until(
        #     expected_conditions.element_to_be_clickable(element))
        wait_time_gen = util.wait_time.generator(self.START_WAIT_TIME,
                                                 self.MAX_INTERVAL_TIME,
                                                 self.CONTEXT_WAIT_TIME)

        error = None
        for i in wait_time_gen:
            try:
                util.element_location_scroll(self.driver, element)
                if not expected_conditions.element_to_be_clickable(element)(self.driver):
                    # move mouse over the element
                    ActionChains(self.driver).move_to_element(element).perform()
                    raise selenium_exceptions.ElementNotInteractableException("element is not clickable")
                element.click()
                break
            except selenium_exceptions.ElementNotInteractableException as err:
                error = err
                time.sleep(i)
            except selenium_exceptions.ElementClickInterceptedException as err:
                # workaround for selenium box where scrolling can cause tooltip to show up.
                # When detected, move the cursor to 0, 0 postion, then move back to the element.
                if "tooltip" not in str(err):
                    raise
                error = err
                location = element.location
                ActionChains(self.driver).move_to_element_with_offset(element,
                                                                      location['x'] * -1,
                                                                      location['y'] * -1).perform()
                time.sleep(i)
                ActionChains(self.driver).move_to_element(element).perform()
        else:
            raise error

    def shadow_root_element(self, element: WebElement, css_selector: str) -> Optional[WebElement]:
        """
            return first element match css selector from shadow root of given web elemenet.

            :param element: web element used to get child element
            :param css_selector: css selector for finding child elements
            :return: first web element match css selector and is child of shadow root of given web element.
                     If not found, None is returned
        """
        return util.get_shadow_root_element(self.driver, element, css_selector)

    def shadow_root_elements(self, element: WebElement, css_selector: str) -> List[WebElement]:
        """
            return elements match css selector from shadow root of given web elemenet.

            :param element: web element used to get child element
            :param css_selector: css selector for finding child elements
            :return: web elements match css selector and is child of shadow root of given web element.  If not found,
                     None is returned
        """
        return util.get_shadow_root_elements(self.driver, element, css_selector)

    def shadow_root_element_text(self, element: WebElement, css_selector: str) -> Optional[str]:
        """
            return text content of the element that match css selector from shadow root of given web elemenet.

            :param element: web element used to get child element
            :param css_selector: css selector for finding child elements
            :return: text content of the web element that match css selector and is child of shadow root of given
                     web element.  If not found, None is returned
        """
        return util.get_shadow_root_element_text(self.driver, element, css_selector)

    def get_text(self, element: WebElement, strict: bool = False) -> Optional[str]:
        """
            Wrapper to return text content of any given element,
            Chrome and firefox webdrivers have inconsistent implementations of getText()

            We use textContent attribute as a fallback.

            Why textContent over innertext?
            https://kellegous.com/j/2013/02/27/innertext-vs-textcontent/

            :param driver: selenium web driver
            :param element: web element to get text content
            :param strict: set to True if you want to strictly return getText()
            :return: text content of the web element
        """
        return util.get_text(self.driver, element, strict)


class ClickContext(Context):
    """
        Click context base class
    """

    def is_enabled(self, timeout: Optional[int] = None) -> bool:
        """
            return click context whether is enable or not.

            :param timeout: time to wait for context to be ready
            :return: True if click context is enable
        """
        raise Exception(f"is_enabled is not implemented for {self.element.tag_name}")

    def link(self, timeout: int) -> str:
        """
            click on given web element in the context

            :param timeout: time to wait for web element.
            :return: String
        """
        raise Exception(f"link is not implemented for {self.element.tag_name}")


class ButtonContext(ClickContext):
    """
        Button context class
    """
    CLICK_CACHE = FifoCache(size_limit=3)
    MIN_WAIT_TIME = 1

    def click(self, timeout: int) -> None:
        """
            click on given web element in the context

            :param timeout: time to wait for web element.
            :return: None
        """
        if self.element.get_attribute("disabled") is not None:
            raise ContextNotFound("Button is not clickable when disabled.")
        element = self.actual_element
        if element in self.CLICK_CACHE and ((time.monotonic() - self.CLICK_CACHE[element]) < self.MIN_WAIT_TIME):
            raise ContextNotFound("interacting with element too quickly")
        self.click_element(element, timeout)
        self.CLICK_CACHE[element] = time.monotonic()

    def is_enabled(self, timeout: Optional[int] = None) -> bool:
        """
            return click context whether is enable or not.

            :param timeout: time to wait for context to be ready
            :return: True if click context is enable
        """
        return self.element.get_attribute("disabled") is None


class LinkContext(ClickContext):
    """
        Web link context class
    """

    def click(self, timeout: int) -> None:
        """
            click on given web element in the context

            :param timeout: time to wait for web element.
            :return: None
        """
        element = self.actual_element
        self.click_element(element, timeout)

    def is_enabled(self, timeout: Optional[int] = None) -> bool:
        """
            return click context whether is enable or not.

            :param timeout: time to wait for context to be ready
            :return: True if click context is enable
        """
        # for now return True
        return True

    def link(self, timeout: int) -> str:
        """
            click on given web element in the context

            :param timeout: time to wait for web element.
            :return: None
        """
        element = self.actual_element
        return element.get_attribute('href')


class InputContext(Context):
    """
        input context base class
    """

    def input_err_msg(self) -> str:
        """
            Base implementation for input context that has no error.


            :return: empty string

        """
        return ""

    def is_enabled(self, timeout: Optional[int] = None) -> bool:
        """
            return whether input context is enabled or not.

            :param timeout: time to wait for context to be ready
            :return: True if input context is enabled
        """
        return self.element.get_attribute("disabled") is None

    def get_tooltip(self, timeout: Optional[int] = None) -> str:
        """
            return tooltip data if present
            :param timeout: time to wait for context to be ready
            :return: return tooltip data if present
        """
        raise Exception(f"get_tooltip method not supported for {self.element.tag_name}")


class SelectContext(Context):
    """
        select context base class
    """

    def select_err_msg(self):
        """
            Base implementation for select context that has no error.


            :return: empty string

        """
        return ""

    def is_enabled(self, timeout: Optional[int] = None) -> bool:
        """
            return whether select context is enabled or not.

            :param timeout: time to wait for context to be ready
            :return: True if select context is enabled
        """
        return self.element.get_attribute("disabled") is None

    def __init__(self,
                 element: WebElement,
                 element_func: Callable = None,
                 user_defined_choices: bool = False,
                 common_info: CommonInfo = None):
        """
            constructor of select context base class

            :param element: web element for the context
            :param element_func: element callback to get actual element for interaction
            :param user_defined_choices: Whether selection choices are user defined.  For
                                         example, Organization is a user defined, as the choices are base
                                         on name of organizations given by user.
            :param common_info:  common information shared to the context

            :return None
        """
        super().__init__(element, element_func, common_info)
        self._user_defined_choices = user_defined_choices

    def get_choice_text(self, choice: WebElement) -> str:
        """
            return text for desired choice element
            :param choice: choice element to get text from
            :return: text for desired choice element.
        """
        try:
            label_element = self.shadow_root_element(choice, "div.UcsRadio-label")
            if label_element:
                # ucs-radio can have label and info section. To keep selection based on div.UcsRadio-label.
                # As in Target Claim Page of Unified edge we can have ucs-localize in ucs-radio.
                return self.get_text(label_element)
        except selenium_exceptions.JavascriptException:
            # In case of div's shadow_root_element will throw JavascriptException as div's dont' have shadowroot.
            pass
        return self.get_text(choice)

    def choices_generator(self,
                          choices: List[Union[str, WebElement]],
                          backward_compatible: bool = True,
                          prefix: str = "",
                          choice_text_func: Callable = None) -> Generator[Tuple[str, Union[str, WebElement]],
                                                                          None,
                                                                          None]:
        """
            yield backward compatible choice text with choice if backward_compatible is True.
            Otherwise, yield original choice text with choice.

            :param choices: list of possible choice
            :param backward_compatible: Whether to include backward compatible choice text or not
            :param prefix: prefix to add to choice text if any
            :param choice_text_func: function to get choice text from choice.

            :return: generator with choice text and choice.
        """

        if choice_text_func is None:
            choice_text_func = self.get_choice_text
        for choice in choices:
            if prefix:
                choice_text = prefix + choice_text_func(choice)
            else:
                choice_text = choice_text_func(choice)
            yield (choice_text, choice)
            if not self._user_defined_choices and backward_compatible:
                old_choices = mapper.select_choice_label_mapper(self.common_info.url,
                                                                choice_text)
                for old_choice in old_choices:
                    yield (old_choice, choice)

    def choices(self,
                enabled: Optional[bool],
                timeout: int,
                backward_compatible: bool = True,
                prefixes: Optional[List[str]] = None) -> List[str]:
        """
            return selection choices

            :param enabled: if None, return all choices.  If True, return enabled choice only.  If False,
                            return disabled choice only.
            :param timeout: time to wait for the web element to be ready
            :param backward_compatible: backward compatibility should be consider or not.
            :param prefixes: Specify the list of prefixes level to view the choices

            :return list of choices for selection
        """
        raise ContextNotFound(f'choices method is not supported for element {self.element.tag_name}')

    def selected(self, timeout: int, backward_compatible: bool = True) -> List[str]:
        """
            return selected choice

            :param timeout: time to wait for the web element to be ready
            :param backward_compatible: backward compatibility should be consider or not.

            :return selected choice
        """
        raise ContextNotFound(f'selected method is not supported for element {self.element.tag_name}')

    def select_with_create(self, timeout: int) -> None:
        """
            select by creating new value.
            For example, select policy reference by creating new policy first

            :param timeout: time to wait for the web element to be ready
            :return None
        """
        raise ContextNotFound(f'select_with_create method is not supported for element {self.element.tag_name}')

    def get_choice_tooltip(self, value: str,
                           timeout: Optional[int] = None,
                           backward_compatible: Optional[bool] = True) -> str:
        """
            return tooltip data of a choice if present
            :param value: choice whose tooltip info needs to be returned
            :param timeout: time to wait for context to be ready
            :param backward_compatible: backward compatibility should be consider or not.
            :return: return tooltip data of a choice if present
        """
        raise ContextNotFound(f'get_choice_tooltip method is not supported for element {self.element.tag_name}')

    def get_selector_cell_tooltip(self,
                                  column_value: str,
                                  column: str,
                                  timeout: Optional[int] = None) -> str:
        """
            Open the selector drawer, filter by column value, hover on the matching cell's column,
            and return tooltip data. Column value is unique per table; tables are searched in order.

            :param column_value: value to filter by in the Name column (e.g. "my-policy" or "org-name/my-policy")
            :param column: column name (e.g., "Name", "Organization", "Description")
            :param timeout: time to wait for drawer and table to be ready (default: CONTEXT_WAIT_TIME)
            :return: tooltip text for the cell
        """
        raise ContextNotFound(
            f'get_selector_cell_tooltip method is not supported for element {self.element.tag_name}')


class SimpleSelectContext(SelectContext):
    """
        simple selection class definition
    """

    def __init__(self,
                 element: WebElement,
                 choices_css_selector: str,
                 selected_css_selector: str,
                 shadow_host: bool = True,
                 allow_no_selection: bool = False,
                 element_func: Callable = None,
                 user_defined_choices: bool = False,
                 common_info: CommonInfo = None):
        """
            constructor of select context base class

            :param element: web element for the context
            :param choices_css_selector: css selector for choices
            :param selected_css_selector: css selector for selected
            :param shadow_host: whether the select item is within the shadow root.
            :param allow_no_selection: True if it is possible for context has no choice selected.
            :param element_func: element callback to get actual element for interaction
            :param user_defined_choices: Whether selection choices are user defined.  For
                                         example, Organization is a user defined, as the choices are base
                                         on name of organizations given by user.
            :param common_info:  common information shared to the context

            :return None
        """
        super().__init__(element, element_func, user_defined_choices, common_info)
        self.choices_css_selector = choices_css_selector
        self.selected_css_selector = selected_css_selector
        self.shadow_host = shadow_host
        self.allow_no_selection = allow_no_selection

    def select(self, value: str, timeout: int, backward_compatible: bool = True) -> None:
        """
            select value of the context

            :param value: value to be selected
            :param timeout: time to wait for the web element to be ready
            :param backward_compatible: backward compatibility should be consider or not.

            :return None
        """
        element = self.actual_element
        # find the corresponding radio element
        if self.shadow_host:
            choices = self.shadow_root_elements(element, self.choices_css_selector)
        else:
            choices = element.find_elements(By.CSS_SELECTOR, self.choices_css_selector)
        choice = None
        choice_text = None
        for choice_text, choice in self.choices_generator(choices, backward_compatible):
            if choice_text == value:
                break
        else:
            raise ValueNotSet(f'Unable to find tab {value}.  Available tabs are {self.choices(None, 0)}')

        wait_time_gen = util.wait_time.generator(self.START_WAIT_TIME,
                                                 self.MAX_INTERVAL_TIME,
                                                 self.CONTEXT_WAIT_TIME)
        selected = None
        for i in wait_time_gen:
            self.click_element(choice, timeout)
            selected = self.selected(timeout=timeout, backward_compatible=backward_compatible)
            if choice_text in selected:
                break
            time.sleep(i)
        else:
            raise ValueNotFound(f'{choice_text} is not selected.  Current selected is {selected}')

    def choices(self,
                enabled: Optional[bool],
                timeout: int,
                backward_compatible: bool = True,
                prefixes: Optional[List[str]] = None) -> List[str]:
        """
            return selection choices

            :param enabled: if None, return all choices.  If True, return enabled choice only.  If False,
                            return disabled choice only.
            :param timeout: time to wait for the web element to be ready
            :param backward_compatible: backward compatibility should be consider or not.
            :param prefixes: Specify the list of prefixes level to view the choices.

            :return list of choices for selection
        """

        if enabled is False:
            return []

        element = self.actual_element

        wait_time_gen = util.wait_time.generator(self.START_WAIT_TIME,
                                                 self.MAX_INTERVAL_TIME,
                                                 self.CONTEXT_WAIT_TIME)
        for i in wait_time_gen:
            if self.shadow_host:
                choices = self.shadow_root_elements(element, self.choices_css_selector)
            else:
                choices = element.find_elements(By.CSS_SELECTOR, self.choices_css_selector)
            if choices:
                break
            time.sleep(i)
        else:
            raise ValueNotFound("Unable to find any available choices")

        return list(map(lambda x: x[0], self.choices_generator(choices,
                                                               backward_compatible)))

    def selected(self, timeout: int, backward_compatible: bool = True) -> List[str]:
        """
            return selected choice

            :param timeout: time to wait for the web element to be ready
            :param backward_compatible: backward compatibility should be consider or not.

            :return selected choice
        """
        element = self.actual_element
        if self.shadow_host:
            choice = self.shadow_root_element(element, self.selected_css_selector)
        else:
            choice = element.find_element(By.CSS_SELECTOR, self.selected_css_selector)
        if choice is None:
            if self.allow_no_selection:
                return []
            raise ValueNotFound("Unable to find selected value.")
        return list(map(lambda x: x[0], self.choices_generator([choice],
                                                               backward_compatible)))


class TextContext(InputContext):
    """
        Text Input context class definition
    """

    def input(self, value: str, timeout: int, verify_value: Optional[Any] = None) -> None:
        """
            input value to given input context

            :param value: value to be input.
            :param timeout: time to wait for the web element to be ready
            :param verify_value: compare the set value with this value \
                to verify if a value has been set correctly in the UI
            :return: None
        """
        element = self.actual_element
        WebDriverWait(self.driver, self.CONTEXT_WAIT_TIME).until(
            expected_conditions.element_to_be_clickable(element))
        value = str(value)
        wait_time_gen = util.wait_time.generator(self.START_WAIT_TIME,
                                                 self.MAX_INTERVAL_TIME,
                                                 self.CONTEXT_WAIT_TIME)
        error = None
        for i in wait_time_gen:
            try:
                util.element_location_scroll(self.driver, element)
                # clear value
                self.click_element(element, timeout)
                action_chains = ActionChains(self.driver)
                current_value = element.get_attribute('value')
                if current_value:
                    for _ in range(len(current_value)):
                        # need to send key by key because sometime
                        # the key are missing when send in one shot.
                        # use right key, because the cursor may not be at the end of input
                        action_chains.send_keys(Keys.RIGHT, Keys.BACKSPACE).perform()

                if value:
                    for char in value:
                        action_chains.send_keys(char).perform()
                set_value = element.get_attribute('value')
                if set_value != value:
                    raise ValueNotSet(f'{set_value} != {value}')
                break
            except (selenium_exceptions.InvalidElementStateException, ValueNotSet) as err:
                error = err
                time.sleep(i)
        else:
            raise error

    def value(self, timeout: int = None) -> str:
        """
            return value in the input field

            :param timeout: time to wait for the web element to be ready
            :return: value in the input field
        """
        element = self.actual_element
        WebDriverWait(self.driver, timeout).until(
            expected_conditions.element_to_be_clickable(element))
        return element.get_attribute('value')


class DropdownContext(SelectContext):
    """
        Dropdown context class definition
    """

    def _render_dropdown_options(self, element):
        """
        Triggers the dropdown options loading if the dropdown element
        has the 'lazyrender' attribute
        """

        if element.get_attribute('lazyrender') is not None:
            element.click()
            time.sleep(0.25)  # Allow time for options to load
            element.click()  # Close the dropdown after triggering rendering

    def select(self, value: str, timeout: int, backward_compatible: bool = True) -> None:
        """
            select value of the context

            :param value: value to be selected
            :param timeout: time to wait for the web element to be ready
            :param backward_compatible: backward compatibility should be consider or not.

            :return None
        """

        element = self.actual_element

        # Trigger the dropdown to load options if it has the 'lazyrender' attribute
        self._render_dropdown_options(element)

        # find available selection
        choices = element.find_elements(By.CSS_SELECTOR, "ucs-dropdown-option")
        for choice_text, choice in self.choices_generator(choices, backward_compatible):
            if choice_text == value:
                break
        else:
            choices_list = list(map(lambda x: x[0], self.choices_generator(choices, backward_compatible)))
            raise ValueNotSet(f'Unable to find drop down item {value}.  Available drop down items are {choices_list}')

        # if the choice is disabled, raise error.
        if choice.get_property('disabled') is True:
            raise ValueError(f'{value} is not selectable as it is disabled.')

        drop_down_element = self.shadow_root_element(element, "div#dropdownBtn")

        self.click_element(drop_down_element, timeout)
        # bring the choice in view
        util.element_location_scroll(self.driver, choice)
        self.click_element(choice, timeout)

        # move cursor back to dropdown element in order to avoid any unnecessary tooltip behaviour.
        action_chains = ActionChains(self.driver)
        action_chains.move_to_element(element).perform()

    def close(self, timeout: int) -> None:
        """
            close the drop down

            :param timeout: time to wait for the web element to be ready
            :return: None
        """
        element = self.actual_element
        if element.get_property("expanded"):
            drop_down_element = self.shadow_root_element(element, "input#button")
            self.click_element(drop_down_element, timeout)

    def choices(self,
                enabled: Optional[bool],
                timeout: int,
                backward_compatible: bool = True,
                prefixes: Optional[List[str]] = None) -> List[str]:
        """
            return selection choices

            :param enabled: if None, return all choices.  If True, return enabled choice only.  If False,
                            return disabled choice only.
            :param timeout: time to wait for the web element to be ready
            :param backward_compatible: backward compatibility should be consider or not.
            :param prefixes: Specify the list of prefixes level to view the choices.

            :return list of choices for selection
        """
        if enabled is False:
            return []

        element = self.actual_element

        wait_time_gen = util.wait_time.generator(self.START_WAIT_TIME,
                                                 self.MAX_INTERVAL_TIME,
                                                 timeout)

        # Trigger the dropdown to load options if it has the 'lazyrender' attribute
        self._render_dropdown_options(element)

        for i in wait_time_gen:
            choices = element.find_elements(
                By.CSS_SELECTOR, "ucs-dropdown-option")

            if choices:
                break
            time.sleep(i)
        else:
            raise ValueNotFound("Unable to find any available choices")

        return list(map(lambda x: x[0], self.choices_generator(choices, backward_compatible)))

    def selected(self, timeout: int, backward_compatible: bool = True) -> List[str]:
        """
            return selected choice

            :param timeout: time to wait for the web element to be ready
            :param backward_compatible: backward compatibility should be consider or not.

            :return selected choice
        """
        element = self.actual_element
        choice = element.find_element(
            By.CSS_SELECTOR, "ucs-dropdown-option[selected]")
        return list(map(lambda x: x[0], self.choices_generator([choice], backward_compatible)))


class RadioContext(SelectContext):
    """
        Radio context class definition
    """

    def select(self, value: str, timeout: int, backward_compatible: bool = True) -> None:
        """
            select value of the context

            :param value: value to be selected
            :param timeout: time to wait for the web element to be ready
            :param backward_compatible: backward compatibility should be consider or not.

            :return None
        """
        element = self.actual_element
        # find the corresponding radio element
        choice = None
        choices = element.find_elements(By.CSS_SELECTOR, "ucs-radio")
        if not choices:
            ucs_form = util.get_shadow_root_element(self.driver, element, "ucs-form")
            choices = ucs_form.find_elements(By.CSS_SELECTOR, "ucs-radio")
        for choice_text, choice in self.choices_generator(choices, backward_compatible):
            if choice_text == value:
                break
        else:
            choices_list = list(map(lambda x: x[0], self.choices_generator(choices, backward_compatible)))
            raise ValueNotSet(f'Unable to find radio button {value}.  Available Radio are {choices_list}')

        wait_time_gen = util.wait_time.generator(self.START_WAIT_TIME,
                                                 self.MAX_INTERVAL_TIME,
                                                 self.CONTEXT_WAIT_TIME)
        selected = None

        # Check and retry mechanism to make sure the desired value is selected.
        # If not selected and time out is hit raise a Value Not Found error.
        for i in wait_time_gen:
            try:
                # for case where the click event listener is part of ucs-radio element
                # Eg: setting breakout port in port policy
                # Click to occur on radio button.
                self.click_element(choice, 0.5)
            except selenium_exceptions.ElementClickInterceptedException:
                # We hit this exception when click event listener is part of the parent div
                # instead of the ucs-radio element itself.
                # Eg: ucs-radio in pools creation, selecting pools type.
                div_element = choice.find_element(By.XPATH, "./..")
                self.click_element(div_element, timeout)

            selected = self.selected(timeout=timeout, backward_compatible=backward_compatible)
            if value in selected:
                break
            time.sleep(i)
        else:
            raise ValueNotFound(f'{value} is not selected.  Current selected is {selected}')

    def choices(self,
                enabled: Optional[bool],
                timeout: int,
                backward_compatible: bool = True,
                prefixes: Optional[List[str]] = None) -> List[str]:
        """
            return selection choices

            :param enabled: if None, return all choices.  If True, return enabled choice only.  If False,
                            return disabled choice only.
            :param timeout: time to wait for the web element to be ready
            :param backward_compatible: backward compatibility should be consider or not.
            :param prefixes: Specify the list of prefixes level to view the choices.

            :return list of choices for selection
        """

        if enabled is False:
            return []

        element = self.actual_element

        wait_time_gen = util.wait_time.generator(self.START_WAIT_TIME,
                                                 self.MAX_INTERVAL_TIME,
                                                 timeout)
        for i in wait_time_gen:
            choices = element.find_elements(By.CSS_SELECTOR, "ucs-radio")
            if choices:
                break
            time.sleep(i)
        else:
            raise ValueNotFound("Unable to find any available choices")

        return list(map(lambda x: x[0], self.choices_generator(choices, backward_compatible)))

    def selected(self, timeout: int, backward_compatible: bool = True) -> List[str]:
        """
            return selected choice

            :param timeout: time to wait for the web element to be ready
            :param backward_compatible: backward compatibility should be consider or not.

            :return selected choice
        """
        element = self.actual_element
        choice = element.find_element(By.CSS_SELECTOR, "ucs-radio[checked]")
        return list(map(lambda x: x[0], self.choices_generator([choice], backward_compatible)))


class CheckboxContext(SelectContext):
    """
        Checkbox context class definition
    """

    def __init__(self,
                 element: WebElement,
                 css_selector: str,
                 element_func: Callable = None,
                 user_defined_choices: bool = False,
                 common_info: CommonInfo = None):
        """
            constructor of select context base class

            :param element: web element for the context
            :param css_selector: css selector string to find checkbox context from element.
            :param element_func: element callback to get actual element for interaction
            :param user_defined_choices: Whether selection choices are user defined.  For
                                         example, Organization is a user defined, as the choices are base
                                         on name of organizations given by user.
            :param common_info:  common information shared to the context

            :return None
        """
        super().__init__(
            element, element_func, user_defined_choices, common_info)
        self.css_selector = css_selector

    def select(self, value: str, timeout: int, backward_compatible: bool = True, verify_selection: bool = True) -> None:
        """
            select value of the context

            :param value: value to be selected
            :param timeout: time to wait for the web element to be ready
            :param backward_compatible: backward compatibility should be consider or not.
            :param verify_selection: If True (Default), after attempting to select the value, a verification step will 
              be performed to ensure the element's 'checked' attribute reflects the intended value. If False, no such
              verification is performed.

            :return None
        """
        element = self.actual_element
        WebDriverWait(self.driver, timeout).until(
            expected_conditions.element_to_be_clickable(element))

        wait_time_gen = util.wait_time.generator(self.START_WAIT_TIME,
                                                 self.MAX_INTERVAL_TIME,
                                                 timeout)

        curr_val = bool(element.get_attribute("Checked"))
        value = bool(value)

        if curr_val != value:
            input_element = self.shadow_root_element(element, self.css_selector)
            error = None
            for i in wait_time_gen:
                try:
                    try:
                        self.click_element(input_element, timeout)
                        if verify_selection:
                            WebDriverWait(self.driver, 5).until(
                                lambda d: bool(element.get_attribute("checked")) == value)
                    except selenium_exceptions.ElementClickInterceptedException:
                        # for checkbox in table modification, parent div intercept checkbox
                        div = element.find_element(By.XPATH, "./..")
                        if "item" in div.get_attribute("class") and div.tag_name == "div":
                            self.click_element(div, timeout)
                            if verify_selection:
                                WebDriverWait(self.driver, 5).until(
                                    lambda d: bool(element.get_attribute("checked")) == value)
                    set_value = bool(element.get_attribute("Checked"))
                    if verify_selection and set_value != value:
                        raise ValueNotSet(f'{set_value} != {value}')
                    break
                except (selenium_exceptions.InvalidElementStateException, ValueNotSet) as err:
                    error = err
                    time.sleep(i)
            else:
                raise error

    def selected(self, timeout: int, backward_compatible: bool = True) -> List[bool]:
        """
            return selected choice

            :param timeout: time to wait for the web element to be ready
            :param backward_compatible: backward compatibility should be consider or not.

            :return selected choice
        """
        element = self.actual_element
        WebDriverWait(self.driver, timeout).until(
            expected_conditions.element_to_be_clickable(element))
        return [bool(element.get_attribute("Checked"))]

    def choices(self,
                enabled: Optional[bool],
                timeout: int,
                backward_compatible: bool = True,
                prefixes: Optional[List[str]] = None) -> List[bool]:
        """
            return selection choices

            :param enabled: if None, return all choices.  If True, return enabled choice only.  If False,
                            return disabled choice only.
            :param timeout: time to wait for the web element to be ready
            :param backward_compatible: backward compatibility should be consider or not.
            :param prefixes: Specify the list of prefixes level to view the choices.

            :return list of choices for selection
        """
        if enabled is False:
            return []
        return [True, False]


class ExpandContext(SelectContext):
    """
            Expand context class definition
        """

    def __init__(self,
                 element: WebElement,
                 element_func: Callable = None,
                 user_defined_choices: bool = False,
                 property_func: Callable = None,
                 common_info: CommonInfo = None):
        """
            constructor of select context base class

            :param element: web element for the context
            :param element_func: element callback to get actual element for interaction
            :param user_defined_choices: Whether selection choices are user defined.  For
                                         example, Organization is a user defined, as the choices are base
                                         on name of organizations given by user.
            :param property_func: property callback to get property which determines the state.
            :param common_info:  common information shared to the context

            :return None
        """
        if property_func:
            self.property_func = property_func
        else:
            self.property_func = lambda: bool(element.get_property("expanded") == 'true')
        super().__init__(
            element, element_func, user_defined_choices, common_info)

    def select(self, value: str, timeout: int, backward_compatible: bool = True) -> None:
        """
            select value of the context

            :param value: value to be selected
            :param timeout: time to wait for the web element to be ready
            :param backward_compatible: backward compatibility should be consider or not.

            :return None
        """
        element = self.actual_element
        WebDriverWait(self.driver, timeout).until(
            expected_conditions.element_to_be_clickable(element))

        wait_time_gen = util.wait_time.generator(self.START_WAIT_TIME,
                                                 self.MAX_INTERVAL_TIME,
                                                 timeout)

        curr_val = self.property_func()

        value = bool(value)

        if curr_val != value:
            self.click_element(self.actual_element, timeout)
            error = None
            for i in wait_time_gen:
                try:
                    set_value = self.property_func()
                    if set_value != value:
                        raise ValueNotSet(f'{set_value} != {value}')
                    break
                except selenium_exceptions.InvalidElementStateException as err:
                    error = err
                    time.sleep(i)
                    try:
                        self.click_element(self.actual_element, timeout)
                    except selenium_exceptions.InvalidElementStateException as err1:
                        error = err1
                except ValueNotSet as err:
                    error = err
                    time.sleep(i)
            else:
                raise error

    def selected(self, timeout: int, backward_compatible: bool = True) -> List[bool]:
        """
            return selected choice

            :param timeout: time to wait for the web element to be ready
            :param backward_compatible: backward compatibility should be consider or not.

            :return selected choice
        """
        element = self.actual_element
        WebDriverWait(self.driver, timeout).until(
            expected_conditions.element_to_be_clickable(element))
        return [self.property_func()]

    def choices(self,
                enabled: Optional[bool],
                timeout: int,
                backward_compatible: bool = True,
                prefixes: Optional[List[str]] = None) -> List[bool]:
        """
            return selection choices

            :param enabled: if None, return all choices.  If True, return enabled choice only.  If False,
                            return disabled choice only.
            :param timeout: time to wait for the web element to be ready
            :param backward_compatible: backward compatibility should be consider or not.
            :param prefixes: Specify the list of prefixes level to view the choices.

            :return list of choices for selection
        """
        if enabled is False:
            return []
        return [True, False]


class ObjRefContext(SelectContext):
    """
        Object reference context class definition.  Mainly for selecting any Intersight object
    """


class TableContext(Context):
    """
        Base class for table context.
    """

    def hover_cell(self,
                   row_index: int,
                   column: str,
                   timeout: int) -> None:
        """
            Get hover data for a cell of a given row index and column

            :param row_index: row index of the table cell
            :param column: column name of the table cell
            :param timeout: time to wait for table to be loaded.

            :return: None
        """
        raise Exception(f"hover_cell method not supported for {self.element.tag_name}.")


class CanvasContext(Context):
    """
        Base class for table context.
    """

    def _drag_and_drop(self,
                       src_element: WebElement,
                       dst_element: WebElement,
                       dst_x_offset: int,
                       dst_y_offset: int) -> None:
        """
            drag and drop src element to dst element with given offset.
            The offset is calculated from top left of the dst element.

            :param src_element: source element to drag
            :param dst_element: destination element to drop to.
            :param dst_x_offset: x coordinate offset from destination element
            :param dst_y_offset: y coordinate offset from destination element
            :return: None
        """

        java_script = '''
            function simulateDragDrop(sourceNode, destinationNode, dstXOffset, dstYOffset) {
                var EVENT_TYPES = {
                    DRAG_END: 'dragend',
                    DRAG_START: 'dragstart',
                    DROP: 'drop'
                }

                function createCustomEvent(type) {
                    var event = new CustomEvent("CustomEvent")
                    event.initCustomEvent(type, true, true, null)
                    event.dataTransfer = {
                        data: {
                        },
                        setData: function(type, val) {
                            this.data[type] = val
                        },
                        getData: function(type) {
                            return this.data[type]
                        }
                    }
                    return event
                }

                function dispatchEvent(node, type, event) {
                    if (node.dispatchEvent) {
                        return node.dispatchEvent(event)
                    }
                    if (node.fireEvent) {
                        return node.fireEvent("on" + type, event)
                    }
                }

                var event = createCustomEvent(EVENT_TYPES.DRAG_START)
                dispatchEvent(sourceNode, EVENT_TYPES.DRAG_START, event)

                var dropEvent = createCustomEvent(EVENT_TYPES.DROP)
                dropEvent.dataTransfer = event.dataTransfer
                var p = destinationNode.getBoundingClientRect()
                dropEvent.x = p['x'] + dstXOffset
                dropEvent.y = p['y'] + dstYOffset


                dispatchEvent(destinationNode, EVENT_TYPES.DROP, dropEvent)

                var dragEndEvent = createCustomEvent(EVENT_TYPES.DRAG_END)
                dragEndEvent.dataTransfer = event.dataTransfer
                dispatchEvent(sourceNode, EVENT_TYPES.DRAG_END, dragEndEvent)
            }

            simulateDragDrop(arguments[0], arguments[1], arguments[2], arguments[3])
        '''

        return self.driver.execute_script(java_script, src_element, dst_element, dst_x_offset, dst_y_offset)

    def _get_tasks_info(self,
                        element: WebElement) -> Mapping[str, Mapping[str, WebElement]]:
        """
            get tasks information from given web element.  The dictionary keys are category and task name

            :param element: element to get tasks information
            :return: dictionary with task category, task name and task element.
        """

        java_script = '''
            function getTasks(element) {
                var categoryList = element.shadowRoot.querySelectorAll("an-workflowdesigner-tasklistcategory")
                var category
                var categoryHeaderText
                var categoryText
                var taskList
                var taskMap
                var task
                var rtrVal = {}
                for (let i = 0; i < categoryList.length; i++) {
                    category =  categoryList[i]
                    categoryHeaderText = category.shadowRoot.querySelector(
                                                        "div:not(.hidden).wrapper div.categoryHeaderText")
                    if (categoryHeaderText) {
                        categoryText = categoryHeaderText.innerText
                        taskList = category.shadowRoot.querySelectorAll("div.outerItem div.taskLeftText")
                        taskMap = {}
                        for (let j = 0; j < taskList.length; j++) {
                            task = taskList[j]
                            taskMap[taskList[j].innerText] = task
                        }
                        if (Object.keys(taskMap).length) {
                            rtrVal[categoryText] = taskMap
                        }
                    }
                }
                return rtrVal
            }

            return getTasks(arguments[0])
        '''
        return self.driver.execute_script(java_script, element)

    def _javascript_attr(self,
                         element: WebElement,
                         attr_name: str) -> Any:
        """
            return web element javascript attribute

            :param element: element to get attribute from
            :param attr_name: attribute name to get
            :return: web element javascript attribute
        """

        return self.driver.execute_script(f"return arguments[0].{attr_name}", element)

    def nodes_info(self) -> Mapping[str, Tuple[str, Mapping[str, Union[int, float]]]]:
        """
            return node name, node label and position mapping table.
            :return: node name, node label and position mapping table.
        """
        raise ContextNotFound(f'nodes_info method is not supported for element {self.element.tag_name}')

    def edges_info(self) -> List[Mapping[str, str]]:
        """
            return list of edges
            :return: list of edges
        """
        raise ContextNotFound(f'edges_info method is not supported for element {self.element.tag_name}')

    def add_task(self,
                 name: str,
                 node_name: Optional[str] = None,
                 x_offset: Optional[int] = None,
                 y_offset: Optional[int] = None) -> None:
        """
            add task to workflow canvas

            :param name: name of task to be added.
            :param node_name: task name to drop the workflow to.  This is mainly for parallel loop or serial loop.
                              But can also be use as drop location.  This is only applicable when x_offset and y_offset
                              is None.
            :param x_offset: x coordinate on where to drop the task.  The coordinate is relative to top left of canvas.
            :param y_offset: y coordinate on where to drop the task.  The coordinate is relative to top left of canvas.

            :return: None
        """
        raise ContextNotFound(f'add_task method is not supported for element {self.element.tag_name}')

    def add_workflow(self,
                     name: str,
                     node_name: Optional[str] = None,
                     x_offset: Optional[int] = None,
                     y_offset: Optional[int] = None) -> None:
        """
            add workflow to workflow canvas

            :param name: name of workflow to be added.
            :param node_name: node name to drop the workflow to.  This is mainly for parallel loop or serial loop.
                              But can also be use as drop location.  This is only applicable when x_offset and y_offset
                              is None.
            :param x_offset: x coordinate on where to drop the workflow.
                             The coordinate is relative to top left of canvas.
            :param y_offset: y coordinate on where to drop the workflow.
                             The coordinate is relative to top left of canvas.

            :return: None
        """
        raise ContextNotFound(f'add_workflow method is not supported for element {self.element.tag_name}')

    def add_operation(self,
                      name: str,
                      node_name: Optional[str] = None,
                      x_offset: Optional[int] = None,
                      y_offset: Optional[int] = None) -> None:
        """
            add workflow to workflow canvas

            :param name: name of workflow to be added.
            :param node_name: node name to drop the workflow to.  This is mainly for parallel loop or serial loop.
                              But can also be use as drop location.  This is only applicable when x_offset and y_offset
                              is None.
            :param x_offset: x coordinate on where to drop the operation.
                             The coordinate is relative to top left of canvas.
            :param y_offset: y coordinate on where to drop the operation.
                             The coordinate is relative to top left of canvas.

            :return: None
        """
        raise ContextNotFound(f'add_operation method is not supported for element {self.element.tag_name}')

    def zoom_out(self) -> bool:
        """
            click zoom out once if it is not disabled
            :return: return True if zoom_out is clicked
        """
        raise ContextNotFound(f'zoom_out method is not supported for element {self.element.tag_name}')

    def zoom_in(self) -> bool:
        """
            click zoom in once if it is not disabled
            :return: return True if zoom_out is clicked
        """
        raise ContextNotFound(f'zoom_in method is not supported for element {self.element.tag_name}')

    def auto_workflow_align(self) -> None:
        """
            click auto workflow align
            :return: None
        """
        raise ContextNotFound(f'auto_workflow_align method is not supported for element {self.element.tag_name}')

    def connect_nodes(self,
                      src_node: str,
                      dst_node: str,
                      success: bool = True,
                      condition_index: int = None) -> None:
        """
            connect nodes in the canvas

            :param src_node: source node to connect
            :param dst_node: destination node to connect
            :param success: True if the connect success path.  Otherwise, connect failure path
            :param condition_index: condition point to connect.  Only applicable to condition task.  Index start with 0
            :return: None
        """
        raise ContextNotFound(f'connect_nodes method is not supported for element {self.element.tag_name}')

    def disconnect_node(self,
                        src_node: str,
                        success: bool = True,
                        condition_index: int = None) -> None:
        """
            disconnect node in the canvas.  return False if edge does not exist

            :param src_node: source node to connect
            :param success: True if the connect success path.  Otherwise, connect failure path
            :param condition_index: condition point to connect.  Only applicable to condition task.  Index start with 0
            :return: None
        """

        raise ContextNotFound(f'disconnect_node method is not supported for element {self.element.tag_name}')

    def add_node(self, node: str) -> None:
        """
            add node to canvas

            :param node: node to add
            :return: None
        """
        raise ContextNotFound(f'add_node method is not supported for element {self.element.tag_name}')

    def delete_node(self, node: str) -> None:
        """
            delete given node from canvas

            :param node: node to delete
            :return: None
        """
        raise ContextNotFound(f'delete_node method is not supported for element {self.element.tag_name}')

    def edit_node(self, node: str) -> None:
        """
            open edit drawer of given node from canvas

            :param node: node to edit
            :return: None
        """
        raise ContextNotFound(f'edit_node method is not supported for element {self.element.tag_name}')

    def expand_node(self, node: str, expand=True) -> None:
        """
            expand given node from canvas

            :param node: node to expand
            :param expand: expand or collapse node
            :return: return True if action is taken to expand or collapse
        """
        raise ContextNotFound(f'expand_node method is not supported for element {self.element.tag_name}')

    def move_node(self, node: str, x_coordinate: int, y_coordinate: int) -> None:
        """
            move given node to given canvas position

            :param node: node to move
            :param x_coordinate: x coordinate.  Scale is 0-100 and from left to right (i.e right most is 0)
            :param y_coordinate: y coordinate.  Scale is 0-100 and from top to bottom (i.e top most is 0)
            :return: None
        """
        raise ContextNotFound(f'move_node method is not supported for element {self.element.tag_name}')

    def delete(self) -> None:
        """
            delete canvas

            :return: None
        """
        raise ContextNotFound(f'delete method is not supported for element {self.element.tag_name}')

    def edit(self) -> None:
        """
            edit canvas

            :return: None
        """
        raise ContextNotFound(f'edit method is not supported for element {self.element.tag_name}')


class DataContext(Context):
    """
        Base class for data context
    """


class DataDictContext(Context):
    """
        Base class for data dictionary context
    """

    def values(self, timeout: int) -> Mapping[str, str]:
        """
            return data in data context

            :param timeout: time to wait for the web element to be ready

            :return: data in data context
        """
        raise Exception(f"values method is not implemented for element {self.element.tag_name}")


class DataValueContext(DataContext):
    """
        Base class for data value context
    """

    def values(self, timeout: int) -> Union[str, List[str]]:
        """
            return text in data context

            :param timeout: time to wait for the web element to be ready

            :return: text in data context
        """
        element = self.actual_element
        return self.get_text(element)

    def scroll_to_bottom(self, timeout: int) -> None:
        """
            scroll the data value to bottom.

            :param timeout: time to wait for the web element to be ready

            :return: None
        """
        raise Exception(f"scroll_to_bottom method is not implemented for element {self.element.tag_name}")


class NotificationContext(Context):
    """
        Base class for notification context.
    """

    def view(self, timeout: int) -> None:
        """
            view notification

            :param timeout: time to wait for web element.
            :return: None
        """
        raise Exception(f"view method is not implemented for element {self.element.tag_name}")

    def text(self, timeout: int) -> None:
        """
            text of notification

            : param timeout: time to wait for web element.
            :return: None
        """
        raise Exception(f"text method is not implemented for element {self.element.tag_name}")


class ErrorContext(Context):
    """
        Base class for error context
    """

    def text(self, timeout: int) -> str:
        """
            return text in error context

            :param timeout: time to wait for the web element to be ready

            :return: text in error context
        """
        raise Exception(f'text method is not supported for element {self.element.tag_name}')


class ContextList:
    """
        base class definition for ContextList.  This is used to hold list of contexts into one object.
        The main purpose to able to aggregate all the information together from the components.

        Currently, only used for data context aggregation
    """

    def __init__(self, element: WebElement = None, allow_empty: bool = False, common_info: CommonInfo = None) -> None:
        """
            constructor of ContextList

            :param element: web element own the context list
            :param common_info:  common information shared to the context
            :return None
        """
        self.contexts = []
        self.element = element
        self.allow_empty = allow_empty
        self.common_info = common_info

    def add(self, contexts: List[Context]) -> None:
        """
            add context list into the current obj

            :params: contexts: contexs to add
            :return: None
        """

        self.contexts.extend(contexts)

    def highlight(self) -> None:
        """
            highlight contexts

            :return: None
        """
        for context in self.contexts:
            context.highlight()

    def clear_highlight(self) -> None:
        """
            clear all highlight

            :return: None
        """
        if self.contexts:
            self.contexts[0].clear_highlight()


class DataDictContextList(ContextList):
    """
        class definition for DataDictContextList.  This is used to hold list of contexts into one object.
        It is mainly use to aggreate data context, so we can group list of contexts together

    """

    def _update(self, rtr_map: dict, item_map: dict) -> dict:
        """
            update recursive dictionary

            :param rtr_map: current dictionary to be updated
            :param item_map: items to be used to update rtr_map
            :return: updated dictionary
        """
        for key, value in item_map.items():
            if isinstance(value, dict):
                rtr_map[key] = self._update(rtr_map.get(key, {}), value)
            else:
                rtr_map[key] = value
        return rtr_map

    def values(self, timeout: int) -> Mapping[str, str]:
        """
            return data in data contexts

            :param timeout: time to wait for the web element to be ready

            :return: data in data contexts
        """

        rtr_map = {}
        for context in self.contexts:
            rtr_map = self._update(rtr_map, context.values(timeout))
        if not rtr_map:
            # no data found.  raise exception so we can retry
            raise ValueNotFound(f"No data found in context {self.contexts}")
        return rtr_map

    def tooltip_choices(self, timeout: Optional[int] = None):
        """
        return tooltip choices
        :param timeout: time to wait for context to be ready
        :return: return tooltip choices
        """
        choices = []
        for context in self.contexts:
            choices.append(context.actual_element.text.split("\n")[0])
        return choices

    def get_choice_tooltip(self, value: str,
                           timeout: Optional[int] = None,
                           backward_compatible: Optional[bool] = True) -> str:
        """
        return tooltip data of a choice if present
        :param value: choice whose tooltip info needs to be returned
        :param timeout: time to wait for context to be ready
        :param backward_compatible: backward compatibility should be consider or not.
        :return: return tooltip data of a choice if present
        """
        for context in self.contexts:
            if context.actual_element.text.split("\n")[0] == value:
                break
        else:
            raise ValueNotFound(f"Unable to find value {value}. Available choices are {self.tooltip_choices()}")

        return context.get_choice_tooltip(timeout)


# type alias
PathContext = Union[str, Tuple[str, ...], None]

InputContextMap = Mapping[str, Mapping[Tuple[str, ...], InputContext]]
ClickContextMap = Mapping[str, Mapping[Tuple[str, ...], ClickContext]]
SelectContextMap = Mapping[str, Mapping[Tuple[str, ...], SelectContext]]
DataContextMap = Mapping[str, Mapping[Tuple[Union[str, int], ...],
                                      Union[DataContext, DataDictContextList, DataDictContext]]]
TableContextMap = Mapping[str, Mapping[Tuple[str, ...], TableContext]]
CanvasContextMap = Mapping[str, Mapping[Tuple[str, ...], CanvasContext]]
NotificationContextMap = Mapping[str, Mapping[str, NotificationContext]]
ErrorContextMap = Mapping[str, Mapping[str, ErrorContext]]


class ChildComponentsInfo:
    """
        class definition to store child components information.
    """

    def __init__(self,
                 shadow_elements: List[WebElement],
                 replace_require: bool = False,
                 path_contexts: List[Union[str, int, Callable]] = None,
                 iframe_replace_require: bool = False) -> None:
        """
            constructor for child componet information

            :param shadow_elements: list of child shadow elements
            :param replace_require: whether to replace existing components with given shadow elements.
            :param path_contexts: additional path contexts to add to the shadow elements.
            :param iframe_replace_require: whether to replace existing components with given shadow elements
                                           cross iframe boundary
            :return: None
        """
        if path_contexts is None:
            path_contexts = []
        self.replace_require = replace_require
        self.iframe_replace_require = iframe_replace_require
        if shadow_elements:
            self.component_info_list = [(path_contexts, shadow_elements)]
        else:
            self.component_info_list = []

    def add(self, shadow_elements: List[WebElement], path_contexts: List[Union[str, int, Callable]] = None) -> None:
        """
            add additional shadow elements with different path contexts
            :param shadow_elements: list of child shadow elements
            :param path_contexts: additional path contexts to add to the shadow elements.
            :return: None
        """
        if path_contexts is None:
            path_contexts = []
        self.component_info_list.append((path_contexts, shadow_elements))


class UIComponent:
    """
        Base class for web componet and external component classes
    """

    def __init__(self,
                 driver: WebDriver,
                 common_info: CommonInfo) -> None:
        """
            constructor for UIComponent
            :param driver: selenium web driver
            :param common_info: common information shared between components.
            :return: None
        """

        self.driver = driver
        self._click_context = None
        self._input_context = None
        self._select_context = None
        self._table_context = None
        self._canvas_context = None
        self._data_context = None
        self._notification_context = None
        self._error_context = None
        self.common_info = common_info

    @property
    def click_context(self) -> ClickContextMap:
        """
            return available click context
            :return: click context dictionary.
        """
        return {}

    @property
    def input_context(self) -> InputContextMap:
        """
            return available input context
            :return: input context dictionary.
        """

        return {}

    @property
    def select_context(self) -> SelectContextMap:
        """
            return available select context
            :return: select context dictionary.
        """

        return {}

    @property
    def table_context(self) -> TableContextMap:
        """
            return available table context
            :return: table context dictionary.
        """
        return {}

    @property
    def canvas_context(self) -> CanvasContextMap:
        """
            return available table context
            :return: table context dictionary.
        """
        return {}

    @property
    def data_context(self) -> DataContextMap:
        """
            return available data context
            :return: data context dictionary.
        """
        return {}

    @property
    def notification_context(self) -> NotificationContextMap:
        """
            return available notfication context
            :return: notificaton context dictionary.
        """
        return {}

    @property
    def error_context(self) -> ErrorContextMap:
        """
            return available error context
            :return: error context dictionary.
        """
        return {}


class PageConfig:
    """
        Base class for UI Page Configuration.
    """


class PageLabels:
    """
        Base class for UI Page Labels. Add only the most basic labels here.
    """
    NAME_LABEL = "Name"
    POLICY_NAME_LABEL = "Policy Name"
    SEARCH_LABEL = "Search"
    CREATE_LABEL = "Create"
    EDIT_LABEL = "Edit"
    EDIT_ASSIGNMENT_LABEL = "Edit Assignment"
    ASSIGN_SERVER_LABEL = "Assign Server"
    DELETE_LABEL = "Delete"
    NEXT_LABEL = "Next"
    BACK_LABEL = "Back"
    SET_LABEL = "Set"
    SAVE_LABEL = "Save"
    ADD_LABEL = "Add"
    CONFIRM_LABEL = "Confirm"
    START_LABEL = "Start"
    CANCEL_LABEL = "Cancel"
    CLOSE_LABEL = "Close"
    CLONE_LABEL = "Clone"
    EXIT_LABEL = "Exit"
    DETACH_LABEL = "Detach"
    ATTACH_LABEL = "Attach"
    TOGGLE_LABEL = "Toggle"
    RADIO_LABEL = "Radio"
    PROCEED_LABEL = "Proceed"
    LEAVE_LABEL = "Leave"
    TABS_LABEL = "Tabs"
    POPUP_LABEL = "Pop up"
    ICON_HELP_LABEL = "icon:help"
    ICON_CLOSE_LABEL = "icon:close"
    ICON_EDIT_LABEL = "icon:edit"
    ICON_PENCIL_LABEL = "icon:pencil"
    ICON_EYE_LABEL = "icon:eye"
    ICON_TRASH_LABEL = "icon:trash"
    ICON_USER_LABEL = "icon:user"
    ICON_FILTER_LABEL = "icon:filter"
    ICON_PLUS_LABEL = "icon:plus"
    ICON_MINUS_LABEL = "icon:minus"
    ICON_ARROW_LABEL = "icon:arrow"
    ICON_REQUESTS_LABEL = "icon:requests"
    ICON_ALARMS_LABEL = "icon:alarms"
    ICON_UP_ARROW_LABEL = "icon:arrow-up"
    ICON_DOWN_ARROW_LABEL = "icon:arrow-down"
    ICON_X_CIRCLE = "icon:x-circle"
    ICON_EYE = "icon:eye"
    ICON_SETTING_LABEL = "icon:setting"
    ICON_CLIPBOARD_LABEL = "icon:clipboard"
    ICON_COPY_LABEL = "icon:copy"
    ICON_DOWNLOAD_LABEL = "icon:download"
    ICON_HELP_LABEL = "icon:help"
    ICON_REFRESH_LABE = "icon:arrow-clockwise"
    ICON_LOADING_LABEL = "icon:loading"
    UCS_MODAL_DATA_CTX_LABEL = "Popup"
    EXPANDED_LABEL = "expanded"
    ICON_ADVISORIES_LABEL = "icon:advisories"
    ADVISORIES_BACK_LABEL = "← Advisories"
    ADVISORIES_TABLE_LABEL = "Advisories"
    ACKNOWLEDGE_LABEL = "Acknowledge"
    UNACKNOWLEDGE_LABEL = "Unacknowledge"
    NAVIGATION_LABEL = "Navigation"
    SERVICES_LABEL = "Services"
    ENABLE_LABEL = "Enable"
    ACTIONS_LABEL = "Actions"
    OK_LABEL = "OK"
    ICON_MORE_LABEL = "icon:more"
    REQUESTS_BACK_LABEL = "← Requests"
    UPGRADE_LABEL = "Upgrade"
    REQUESTS_LABEL = "Requests"
    EXPAND_ICON_LABEL = 'icon:expand'
    COLLAPSE_ICON_LABEL = 'icon:collapse'
    SEARCH_RESULTS_LABEL = "Search Results"
    CONTINUE_LABEL = "Continue"
    CLONE_AND_DEPLOY_PROFILES_LABEL = "Clone and Deploy Profiles"
    # 'UCSC845A' - A standalone Cisco AI 845A Server Family.
    SERVER_FAMILY_UCS_C845A_LABEL = "UCSC845A"

class CustomRemoteDisconnected(Exception):
    """
        Exception for RemoteDisconnection
    """


def find_possible_types(field_type: Any, is_list: bool = False) -> List[Tuple[bool, Any]]:
    """
        return possible types base on type annotation

        :param field_type: field type to find the possible type
        :param is_list: True if the type is list

        :return: list of possible type and whether the possible type is a list

    """
    type_args = getattr(field_type, "__args__", None)
    if type_args:
        rtr_list = []
        is_list = is_list or getattr(field_type, "__origin__", None) == list
        for type_arg in type_args:
            if not isinstance(type_arg, type(None)):
                rtr_list.extend(find_possible_types(type_arg, is_list))
        return rtr_list

    return [(is_list, field_type)]


def nested_dataclass(*args, **kwargs) -> Callable:
    """
        decorator for nested dataclass definition

        :return decorator function
    """

    def wrapper(cls):
        choices_map = kwargs.pop("choices_map", {})
        cls = dataclass(cls, **kwargs)
        original_init = cls.__init__

        def __init__(self, *inner_args, **inner_kwargs):
            for name, value in inner_kwargs.items():
                if isinstance(value, list):
                    possible_type_list = []
                    new_list = []
                    for entry in value:
                        actual_type = None
                        if isinstance(entry, dict):
                            if not possible_type_list:
                                field_type = cls.__annotations__.get(
                                    name, None)
                                possible_types = find_possible_types(
                                    field_type)
                                for is_list, possible_type in possible_types:
                                    if is_list and is_dataclass(possible_type):
                                        possible_type_list.append(possible_type)
                                if len(possible_type_list) == 0:
                                    raise Exception(
                                        f"Unable to decode value {value} for {cls}")
                            if len(possible_type_list) == 1:
                                actual_type = possible_type_list[0]
                            elif not actual_type:
                                if choices_map:
                                    for possible_type in possible_type_list:
                                        # check if it is subset of entry
                                        if possible_type in choices_map:
                                            found = False
                                            for c_key, c_value in choices_map[possible_type].items():
                                                if c_key in entry and entry[c_key] == c_value:
                                                    found = True
                                                else:
                                                    found = False
                                                    break
                                            if found:
                                                actual_type = possible_type
                                                break
                                    else:
                                        # no match found
                                        possible_keys = []
                                        for possible_type in possible_type_list:
                                            if possible_type in choices_map:
                                                possible_keys.append(choices_map[possible_type])
                                        raise Exception(
                                            f"Unable to decode value {value} to one of \
                                              possible values with key {possible_keys}")
                                else:
                                    raise Exception(f"Multiple possible type {possible_type_list} for value {value}")

                            new_list.append(actual_type(**entry))
                        else:
                            # raw data
                            new_list.append(entry)
                    inner_kwargs[name] = new_list
                elif isinstance(value, dict):
                    field_type = cls.__annotations__.get(name, None)
                    possible_type_list = []
                    possible_types = find_possible_types(field_type)
                    for is_list, possible_type in possible_types:
                        if not is_list and is_dataclass(possible_type):
                            possible_type_list.append(possible_type)

                    if len(possible_type_list) == 0:
                        raise Exception(
                            f"Unable to decode value {value} for {cls}")
                    if len(possible_type_list) == 1:
                        actual_type = possible_type_list[0]
                    else:
                        if choices_map:
                            for possible_type in possible_type_list:
                                # check if all the keys,value pair match in dict entry
                                if possible_type in choices_map:
                                    found = False
                                    for c_key, c_value in choices_map[possible_type].items():
                                        if c_key in entry and entry[c_key] == c_value:
                                            found = True
                                        else:
                                            found = False
                                            break
                                    if found:
                                        actual_type = possible_type
                                        break
                            else:
                                # no match found
                                possible_keys = []
                                for possible_type in possible_type_list:
                                    if possible_type in choices_map:
                                        possible_keys.append(choices_map[possible_type])
                                raise Exception(
                                    f"Unable to decode value {value} to one of \
                                      possible values with key {possible_keys}")
                        else:
                            raise Exception(f"Multiple possible type {possible_type_list} for value {value}")

                    new_obj = actual_type(**value)
                    inner_kwargs[name] = new_obj
            original_init(self, *inner_args, **inner_kwargs)

        cls.__init__ = __init__
        return cls

    return wrapper(args[0]) if args else wrapper


def context_retry(timeout_position: int,
                  ignore_error: bool = False,
                  default_timeout: int = None) -> Callable:
    """
        decorator for retry context.  The decorator basically will rescan the page until
        given context is found and executed or timeout.

        :param timeout_position: timeout variable position in the method call
        :param ignore_error: ignore exception after timeout
        :param default_timeout: default timeout value for the method.  If None, global timeout is used.

    """

    def context_retry_func(func: Callable) -> Callable:
        """
            context retry decorator wrapper definition

            :param func: method to be called for the context.
            :returns: return wrapper function which will retry until context found and method executed
        """

        @wraps(func)
        def func_wrapper(*args, **kargs) -> Optional[str]:
            """
                retry function definition.  The logic for retry is basically the following

                1. Find context given in component manager.
                2. If more than 1 context found, raise an exception
                3. If no context found, sleep and retry from step 1.
                4. Execute given method.
                5. return if successful
                6. If error is retriable error, sleep and retry from step 1.
                7. If not, raise an exception.

                :returns: error string or None
            """

            self = args[0]
            if len(args) > timeout_position:
                timeout = args[timeout_position]
                if timeout is None:
                    timeout = self.timeout
            else:
                timeout = kargs.get("timeout", default_timeout)
                if timeout is None:
                    timeout = self.timeout
                kargs["timeout"] = timeout

            wait_time_gen = util.wait_time.generator(Context.START_WAIT_TIME,
                                                     Context.MAX_INTERVAL_TIME,
                                                     timeout)
            error = None
            context_type = self.CONTEXT_NAME
            debug = self.log(log_level=logging.DEBUG)
            if debug:
                self.log(f"Processing {context_type} with context {self.context} path context {self.path_contexts}",
                         logging.DEBUG)

            try:
                while wait_time_gen:
                    start_time = time.monotonic()
                    try:
                        if self.context is None:
                            info = getattr(self._component_manager, context_type)
                            if len(info) == 0:
                                raise ContextNotFound(
                                    f"No context found in {context_type}.")
                            if len(info) > 1:
                                raise ContextNotFound(
                                    f"Please make sure context is set to one of the value {info.keys()}.")
                            info = next(iter(info.values()))
                        else:
                            info = getattr(self._component_manager,
                                           context_type).get(self.context, None)
                            if info is None:
                                new_context = mapper.LABEL_MAPPER[context_type](
                                    self._component_manager.url_logged,
                                    self.context)
                                if new_context:
                                    info = getattr(self._component_manager, context_type).get(
                                        new_context, None)
                                if info is None:
                                    contexts = list(getattr(self._component_manager, context_type))
                                    raise ContextNotFound(
                                        f"{self.context} is not found.  Available context are {contexts}")

                                self.log(f"Remap context '{self.context}' to '{new_context}' for {context_type}")

                        if len(info) != 1 or self.path_contexts is not None:
                            path_contexts = self.path_contexts
                            if self.path_contexts is None:
                                raise ContextNotFound(
                                    f"More than 1 contexts found for context '{self.context}'"
                                    f" of type '{context_type}' but None were specified."
                                    " Please specify one using an appropriate path_context."
                                    f" Available path_contexts are {list(info)}")
                            if path_contexts in info:
                                context = info[path_contexts]
                            else:
                                # check if we need to remap label
                                new_path_contexts = mapper.PATH_LABEL_MAPPER[context_type](
                                    self._component_manager.url_logged,
                                    path_contexts)
                                if new_path_contexts is not None:
                                    path_contexts = new_path_contexts
                                    self.log(
                                        f"Remap path context {path_contexts} to {new_path_contexts} for {context_type}")

                                if path_contexts in info:
                                    context = info[path_contexts]
                                else:
                                    if not path_contexts:
                                        # path_contexts is empty, so only exact match is possible.
                                        raise ContextNotFound(
                                            f"path_context {self.path_contexts} not found for context '{self.context}'"
                                            f" of type '{context_type}'. Available path_contexts are {list(info)}")
                                    # check if we can do partial map
                                    matched_contexts = []
                                    path_contexts_set = set(path_contexts)

                                    for info_path_contexts, info_context in info.items():
                                        if path_contexts_set.issubset(info_path_contexts):
                                            matched_contexts.append(info_context)
                                            if len(matched_contexts) > 1:
                                                # more than 1 is found, so break
                                                break

                                    if len(matched_contexts) != 1:
                                        raise ContextNotFound(
                                            f"path_context {self.path_contexts} not found for context '{self.context}'"
                                            f" of type '{context_type}'."
                                            f" Available path_contexts are {list(info.keys())}")

                                    context = matched_contexts[0]
                        else:
                            context = next(iter(info.values()))
                        self.curr_context = context
                        self._iframe_manager.iframes = context.common_info.iframes
                        ret_val = func(*args, **kargs)
                        util.report_memory_failure(self.driver, self.log)
                        if qali_globals.ui[0].coverage_enabled:  # If coverage is enabled
                            # Verify if the time since the last capture is less than the threshold (10 minutes)
                            # For long-running tests, a large amount of coverage data can accumulate in the browser,
                            # potentially causing it to crash and leading to test failures.
                            # To prevent this, coverage data is captured every 10 minutes.
                            # Here First UI object is used because no matter how many UI object we create in one runtest
                            # Session all will have same options available
                            for ui_obj in qali_globals.ui:
                                if time.time() - ui_obj.last_coverage_capture_time > \
                                        ui_obj.coverage_capture_threshold:
                                    ui_obj.capture_ui_function_coverage(store_coverage_data=True)
                        return ret_val
                    except (selenium_exceptions.StaleElementReferenceException,
                            selenium_exceptions.ElementClickInterceptedException,
                            selenium_exceptions.NoSuchElementException,
                            selenium_exceptions.ElementNotInteractableException,
                            selenium_exceptions.TimeoutException,
                            selenium_exceptions.MoveTargetOutOfBoundsException,
                            ContextNotFound,
                            ValueNotFound,
                            ValueNotSet,
                            ReturnErrorMsg,
                            selenium_exceptions.WebDriverException) as err:
                        # page need to be refreshed since element is not available
                        error = err
                        if debug:
                            self.log(f"{context_type} with context {self.context} path context {self.path_contexts} \
                                temporary fail with {type(err).__name__} - {err}", logging.DEBUG)
                    except Exception:
                        self.screenshot(f"Interaction on {context_type} {self.context}")
                        raise
                    self._component_manager.rescan_page()
                    util.wait_time.time_took = time.monotonic() - start_time
                    try:
                        wait_time = next(wait_time_gen)
                    except StopIteration:
                        if ignore_error:
                            return None
                        if isinstance(error, ReturnErrorMsg):
                            return str(ReturnErrorMsg)
                        self.screenshot(f"Interaction on {context_type} {self.context}")
                        raise error

                    time.sleep(wait_time)
            except Exception as exception_err:
                page_errors = self.page_errors(text=True)
                if page_errors:
                    raise PageError(page_errors) from exception_err
                raise exception_err
            return None

        return func_wrapper

    return context_retry_func


class ContextManager:
    """
        Base class for Context Manager.  (i.e ClickMaanger, InputManager, etc)
    """
    CONTEXT_NAME = ''
    mask_pattern = re.compile("[pP]assword")

    def __init__(self,
                 context: str,
                 path_contexts: PathContext,
                 timeout: int,
                 component_manager: "ComponentManager",
                 iframe_manager: "IframeManager",
                 log: Callable,
                 screenshot: Callable,
                 page_errors: Callable) -> None:
        """
            init fucntion for Input manager

            :param context: context for input action
            :param path_contexts: path context for input action.  This is mainly used as tie breaker
            :param timeout: time to wait for context to be ready
            :param component_manager:  component manager instance
            :param iframe_manager:  iframe manager instance
            :param log: logging function
            :param screenshot: screenshot function

            :return: None

        """
        self.context = context
        if path_contexts is not None:
            if isinstance(path_contexts, (str, int)):
                path_contexts = (path_contexts,)
            elif not isinstance(path_contexts, tuple):
                raise Exception(f"path_context can only be string or tuple or integer.\n"
                                f"Current path_context type is {type(path_contexts)}")
        self.path_contexts = path_contexts

        self.timeout = timeout
        self._component_manager = component_manager
        self.driver = component_manager.driver
        self._iframe_manager = iframe_manager
        self.log = log
        self.screenshot = screenshot
        self.curr_context = None
        self.page_errors = page_errors

    @property
    def context_name(self) -> str:
        """
            return context name of the manager

            :return: context name
        """

        if self.path_contexts is None:
            return self.context
        return str((self.context, self.path_contexts))

    def exist(self) -> bool:
        """
            return True if given table context exist.

            :return: True if given table context exist.

        """
        return context_exist(self, self.CONTEXT_NAME)

    def not_exist(self) -> bool:
        """
            return True if context does not exist in the UI
            :return: True if context does not exist
        """
        return not context_exist(self, self.CONTEXT_NAME)

    @context_retry(1)
    def highlight(self, timeout: Optional[int] = None) -> None:
        """
            highlight context

            :param timeout: time to wait for table to be loaded.
            :return: None
        """
        self.curr_context.highlight()

    @context_retry(1)
    def clear_highlight(self, timeout: Optional[int] = None) -> None:
        """
            clear all highlight

            :param timeout: time to wait for table to be loaded.
            :return: None
        """
        self.curr_context.clear_highlight()


def context_exist(obj: ContextManager, context_type: str) -> bool:
    """
        utility function to check if context exist in component manager.

        :param obj: context manager instance
        :param context_type: context variable to look up in component manager.

        :return True if context exist in component manager

    """
    if obj.context is None:
        info = getattr(obj._component_manager, context_type)
        if len(info) == 1:
            info = next(iter(info.values()))
        else:
            info = None
    else:
        info = getattr(obj._component_manager,
                       context_type).get(obj.context, None)
        if info is None:
            new_context = mapper.LABEL_MAPPER[context_type](
                obj._component_manager.url_logged,
                obj.context)
            if new_context:
                info = getattr(obj._component_manager,
                               context_type).get(new_context, None)

    if info is None:
        return False

    if len(info) != 1 or obj.path_contexts:
        if obj.path_contexts is None:
            return False
        if obj.path_contexts not in info:
            new_path_contexts = mapper.PATH_LABEL_MAPPER[context_type](
                obj._component_manager.url_logged,
                obj.path_contexts)
            if new_path_contexts is None:
                path_contexts = obj.path_contexts
            else:
                if new_path_contexts in info:
                    # replace label is found in the key.  So return True
                    return True
                path_contexts = new_path_contexts

            # try partial match
            matched_contexts = []
            path_contexts_set = set(path_contexts)
            for info_path_contexts, info_context in info.items():
                if path_contexts_set.issubset(info_path_contexts):
                    matched_contexts.append(info_context)
                    if len(matched_contexts) > 1:
                        # more than 1 is found, so break
                        return False
            if len(matched_contexts) != 1:
                return False
    return True
