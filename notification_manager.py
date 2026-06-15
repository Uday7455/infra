"""
Notficaiton Manager definitions
"""
from typing import List, Tuple, Optional
from qali.intersight.gui.model_util import context_retry
from qali.intersight.gui.model_util import ContextManager


class NotificationManager(ContextManager):
    """
        Notficaiton Manager class definition

        Notficaiton Manager is responsible to find/retry notification context interaction.

        The manager object is created when notification_ctx is access from Intersight UI object.
    """

    CONTEXT_NAME = "notification_context"

    def repr(self) -> str:
        """
            return representation string of notification context

            :return: representation string of notification context
        """
        if self.path_contexts is None:
            return str(("notification", self.context))
        return str(("notification", (self.context, self.path_contexts)))

    @context_retry(1)
    def close(self, timeout: Optional[int] = None) -> None:
        """
            close notification context

            :param timeout: time to wait for context to be ready
            :return: None
        """
        self.curr_context.close(timeout)
        self.log("Closed notification '{0}'".format(self.context_name))

    @context_retry(1)
    def details(self, timeout: Optional[int] = None) -> str:
        """
            get details from notification context

            :param timeout: time to wait for context to be ready
            :return: None
        """
        rtr = self.curr_context.details(timeout)
        self.log("Notification '{0}' details: {1}".format(self.context_name, rtr))
        return rtr

    @context_retry(1, ignore_error=True, default_timeout=2)
    def close_if_exist(self, timeout: int = 2) -> None:
        """
            close notification context if the context exist

            :param timeout: time to wait for context to be ready
            :return: None
        """
        try:
            self.curr_context.close(timeout)
            self.log("Closed notification '{0}'".format(self.context_name))
        except Exception:
            pass

    def close_all(self, rescan: bool = True) -> List[Tuple[str, str]]:
        """
            close all notification context if the context exist.

            if context is None, all notifciations are closed.
            If context is given, only particular type of notification will be closed.
            Path context has no meaning in close all.  If specific path context is required, use
            close method instead.

            :param rescan: rescan for any new notification
            :return: notifications closed by the method
        """
        if rescan:
            # clear up notification context, because there might be new one
            self._component_manager.rescan_page()
        notification_closed = []
        if self.context is None:
            # close all notification
            for msg_type, msg_map in self._component_manager.notification_context.items():
                for msg, notification_context in msg_map.items():
                    notification_closed.append((msg_type, msg))
                    # switch to right iframe to close notification
                    self._iframe_manager.iframes = notification_context.common_info.iframes
                    try:
                        notification_context.close(0)
                        self.log("Closed notification '{0}'".format((msg_type, msg)))
                    except Exception:
                        pass
        elif self.context in self._component_manager.notification_context:
            for msg, notification_context in self._component_manager.notification_context[self.context].items():
                notification_closed.append((self.context, msg))
                # switch to right iframe to close notification
                self._iframe_manager.iframes = notification_context.common_info.iframes
                try:
                    notification_context.close(0)
                    self.log("Closed notification '{0}'".format((self.context, msg)))
                except Exception:
                    pass
        return notification_closed

    def get_notifications(self, rescan: bool = True) -> List[Tuple[str, str]]:
        """
            get_notifcation of given context

            if context is None, all notificiations will be returned.
            If context is given, only particular type of notification will be returned
            Path context has no meaning in this method.

            :param rescan: rescan for any new notification
            :return: list of notifications 
        """
        notification_list = []
        if rescan:
            # clear up notification context, because there might be new one
            self._component_manager.rescan_page()
        if self.context is None:
            for msg_type, msg_map in self._component_manager.notification_context.items():
                for msg in msg_map:
                    notification_list.append((msg_type, msg[-1]))
        else:
            msg_map = self._component_manager.notification_context.get(self.context, {})
            for msg in msg_map:
                notification_list.append((self.context, msg[-1]))
        return notification_list

    @context_retry(1)
    def text(self, timeout: Optional[int] = None) -> str:
        """
            get text from notification context

            :param timeout: time to wait for context to be ready
            :return: None
        """
        rtr = self.curr_context.text(timeout)
        self.log("Notification '{0}' text: {1}".format(self.context_name, rtr))
        return rtr
