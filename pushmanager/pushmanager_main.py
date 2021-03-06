#!/usr/bin/env python
import os

import pushmanager.core.db as db
import tornado.httpserver
import tornado.web
import pushmanager.ui_methods as ui_methods
import pushmanager.ui_modules as ui_modules
from pushmanager.core import pid
from pushmanager.core.application import Application
from pushmanager.core.git import GitQueue
from pushmanager.core.mail import MailQueue
from pushmanager.core.rb import RBQueue
from pushmanager.core.settings import Settings
from pushmanager.core.util import get_servlet_urlspec
from pushmanager.core.xmppclient import XMPPQueue
from pushmanager.handlers import CheckSitesBookmarkletHandler
from pushmanager.handlers import CreateRequestBookmarkletHandler
from pushmanager.handlers import LoginHandler
from pushmanager.handlers import LogoutHandler
from pushmanager.handlers import NullRequestHandler
from pushmanager.handlers import RedirHandler
from pushmanager.handlers import SamlACSHandler
from pushmanager.servlets.addrequest import AddRequestServlet
from pushmanager.servlets.api import APIServlet
from pushmanager.servlets.blesspush import BlessPushServlet
from pushmanager.servlets.checklist import ChecklistServlet
from pushmanager.servlets.checklist import ChecklistToggleServlet
from pushmanager.servlets.commentrequest import CommentRequestServlet
from pushmanager.servlets.conflictcheck import ConflictCheckServlet
from pushmanager.servlets.delayrequest import DelayRequestServlet
from pushmanager.servlets.deploypush import DeployPushServlet
from pushmanager.servlets.discardpush import DiscardPushServlet
from pushmanager.servlets.discardrequest import DiscardRequestServlet
from pushmanager.servlets.editpush import EditPushServlet
from pushmanager.servlets.livepush import LivePushServlet
from pushmanager.servlets.msg import MsgServlet
from pushmanager.servlets.newpush import NewPushServlet
from pushmanager.servlets.newrequest import NewRequestServlet
from pushmanager.servlets.pickmerequest import PickMeRequestServlet
from pushmanager.servlets.pickmerequest import UnpickMeRequestServlet
from pushmanager.servlets.pingme import PingMeServlet
from pushmanager.servlets.push import PushServlet
from pushmanager.servlets.pushbyrequest import PushByRequestServlet
from pushmanager.servlets.pushes import PushesServlet
from pushmanager.servlets.pushitems import PushItemsServlet
from pushmanager.servlets.removerequest import RemoveRequestServlet
from pushmanager.servlets.request import RequestServlet
from pushmanager.servlets.requests import RequestsServlet
from pushmanager.servlets.smartdest import SmartDestServlet
from pushmanager.servlets.testtag import TestTagServlet
from pushmanager.servlets.summaryforbranch import SummaryForBranchServlet
from pushmanager.servlets.undelayrequest import UndelayRequestServlet
from pushmanager.servlets.userlist import UserListServlet
from pushmanager.servlets.verifyrequest import VerifyRequestServlet


# Servlet dispatch rules
def get_url_specs():
    url_specs = [
        (r'/', SmartDestServlet),
        (r'favicon.*', NullRequestHandler),
        (CreateRequestBookmarkletHandler.url, CreateRequestBookmarkletHandler),
        (CheckSitesBookmarkletHandler.url, CheckSitesBookmarkletHandler),
        (r'/login', LoginHandler),
        (r'/logout', LogoutHandler),
        (r'/acs', SamlACSHandler),
    ]
    for servlet in (APIServlet,
                    ChecklistServlet,
                    ChecklistToggleServlet,
                    ConflictCheckServlet,
                    RequestServlet,
                    RequestsServlet,
                    NewRequestServlet,
                    PickMeRequestServlet,
                    UnpickMeRequestServlet,
                    AddRequestServlet,
                    RemoveRequestServlet,
                    VerifyRequestServlet,
                    DiscardRequestServlet,
                    DelayRequestServlet,
                    UndelayRequestServlet,
                    CommentRequestServlet,
                    PingMeServlet,
                    PushServlet,
                    PushesServlet,
                    EditPushServlet,
                    DiscardPushServlet,
                    DeployPushServlet,
                    BlessPushServlet,
                    LivePushServlet,
                    NewPushServlet,
                    PushItemsServlet,
                    PushByRequestServlet,
                    UserListServlet,
                    SummaryForBranchServlet,
                    MsgServlet,
                    TestTagServlet):
        url_specs.append(get_servlet_urlspec(servlet))
    return url_specs


class PushManagerApp(Application):
    name = "main"

    def __init__(self):
        Application.__init__(self)
        self.redir_port = Settings['main_app']['redir_port']
        self.redir_app = tornado.web.Application(
            [
                (r'/(.*)', RedirHandler),
            ],
        )
        self.main_app = tornado.web.Application(
            get_url_specs(),
            # Server settings
            static_path = os.path.join(os.path.dirname(__file__), "static"),
            template_path = os.path.join(os.path.dirname(__file__), "templates"),
            login_url = "/login",
            cookie_secret = Settings['cookie_secret'],
            ui_modules = ui_modules,
            ui_methods = ui_methods,
            autoescape = None,
        )

    def start_services(self):
        # HTTPS server
        sockets = tornado.netutil.bind_sockets(self.port, address=Settings['main_app']['servername'])
        redir_sockets = tornado.netutil.bind_sockets(self.redir_port, address=Settings['main_app']['servername'])

        # Start the mail, git, reviewboard and XMPP queue handlers
        worker_pids = []
        worker_pids.extend(MailQueue.start_worker())
        worker_pids.extend(RBQueue.start_worker())
        worker_pids.extend(XMPPQueue.start_worker())
        worker_pids.extend(GitQueue.start_worker())
        for worker_pid in worker_pids:
            pid.write(self.pid_file, append=True, pid=worker_pid)
        self.queue_worker_pids.extend(worker_pids)

        tornado.process.fork_processes(Settings['tornado']['num_workers'])

        server = tornado.httpserver.HTTPServer(self.main_app, ssl_options={
                'certfile': Settings['main_app']['ssl_certfile'],
                # This really should be read into a string so we can drop privileges
                # after reading the key but before starting the server, but Python
                # doesn't let us use strings for keys until Python 3.2 :(
                'keyfile': Settings['main_app']['ssl_keyfile'],
                })
        server.add_sockets(sockets)

        # HTTP server (to redirect to HTTPS)
        redir_server = tornado.httpserver.HTTPServer(self.redir_app)
        redir_server.add_sockets(redir_sockets)


def main():
    app = PushManagerApp()
    db.init_db()
    app.run()


if __name__ == '__main__':
    main()
