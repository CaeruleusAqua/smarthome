#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2018-      Martin Sinn                         m.sinn@gmx.de
#########################################################################
#  This file is part of SmartHomeNG.
#
#  SmartHomeNG is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  SmartHomeNG is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with SmartHomeNG.  If not, see <http://www.gnu.org/licenses/>.
#########################################################################


import os
import logging
import json
import cherrypy

import lib.shyaml as shyaml

import jwt
from .rest import RESTResource


class LoggersController(RESTResource):

    logging_config = None

    def __init__(self, module):
        self._sh = module._sh
        self.module = module
        self.base_dir = self._sh.get_basedir()
        self.logger = logging.getLogger(__name__.split('.')[0] + '.' + __name__.split('.')[1] + '.' + __name__.split('.')[2][4:])
        self.etc_dir = self._sh._etc_dir

        return


    def save_logging_config(self, create_backup=False):
        """
        Save dict to logging.yaml
        """
        if self.logging_config is not None:
            self.logging_config['shng_version'] = self._sh.version.split('-')[0][1:]
            conf_filename = os.path.join(self.etc_dir, 'logging')
            shyaml.yaml_save_roundtrip(conf_filename, self.logging_config, create_backup=create_backup)
        return


    def load_logging_config(self):
        """
        Load config from logging.yaml to a dict

        If logging.yaml does not contain a 'shng_version' key, a backup is created
        """
        conf_filename = os.path.join(self.etc_dir, 'logging')
        result = shyaml.yaml_load(conf_filename + '.yaml')

        return result


    def load_logging_config_for_edit(self):
        """
        Load config from logging.yaml to a dict

        If logging.yaml does not contain a 'shng_version' key, a backup is created
        """
        conf_filename = os.path.join(self.etc_dir, 'logging')
        self.logging_config = shyaml.yaml_load_roundtrip(conf_filename)
        self.logger.info("load_logging_config: shng_version={}".format(self.logging_config.get('shng_version', None)))

        if self.logging_config.get('shng_version', None) is None:
            self.logging_config['shng_version'] = self._sh.version.split('-')[0][1:]
            self.save_logging_config(create_backup=True)

        return


    def get_active_loggers(self):

        loggerlist = []
        try:
            wrk_loggerDict = logging.Logger.manager.loggerDict
            for l in dict(wrk_loggerDict):
                lg = logging.Logger.manager.loggerDict[l]
                try:
                    not_conf = lg.not_conf
                except:
                    not_conf = False
                if not_conf:
                    self.logger.info(f"get_active_loggers: not_conf {l=} - {lg=}")
                else:
                    try:
                        h = lg.handlers
                    except:
                        h = []
                    if len(h) > 0:
                        # handlers do exist
                        if (len(h) > 1) or (len(h) == 1 and str(h[0]) != '<NullHandler (NOTSET)>'):
                            loggerlist.append(l)
                            # self.logger.info("ld Handler = {} h = {} -> {}".format(l, h, lg))
                        else:
                            pass
                            #self.logger.info(f"get_active_loggers: {l} - Not len(h) > 1) or (len(h) == 1 and str(h[0])")
                    else:
                        # no handlers exist
                        try:
                            lv = lg.level
                        except:
                            lv = 0
                        if lv > 0:
                            loggerlist.append(l)
                            # self.logger.info("ld Level   = {}, lv = {} -> {}".format(l, lv, lg))
                        else:
                            pass
                            loggerlist.append(l)
                            #self.logger.info(f"get_active_loggers: {l} - {lv=} - {wrk_loggerDict[l]}")
        except Exception as e:
            self.logger.exception("Logger Exception: {}".format(e))

        return sorted(loggerlist)


    def set_active_logger_level(self, logger, level):

        if level is not None:
            lg = logging.getLogger(logger)
            lglevel = logging.getLevelName(level)
            oldlevel = logging.getLevelName(lg.level)

            lg.setLevel(lglevel)
            self.logger.notice(f"Logger '{logger}' changed from {oldlevel} to {level}")

            self.load_logging_config_for_edit()
            try:
                oldlevel = self.logging_config['loggers'][logger]['level']
            except:
                oldlevel = None
            if oldlevel != None:
                self.logging_config['loggers'][logger]['level'] = level
                self.save_logging_config()
                #self.logger.info("Saved changed logger configuration to ../etc/logging.yaml}")
                return True
        return False

    # -----------------------------------------------------------------------------------


    def get_logger_active_configuration(self, loggername=None):

        active = {}
        active_logger = logging.getLogger(loggername)
        active['disabled'] = active_logger.disabled
        active['level'] = self._sh.logs.get_shng_logging_levels().get(active_logger.level, 'UNKNOWN_'+str(active_logger.level))
        active['filters'] = active_logger.filters

        hl = []
        bl = []
        for h in active_logger.handlers:
            hl.append(h.__class__.__name__)
            try:
                bl.append(h.baseFilename)
            except:
                bl.append('')

        active['handlers'] = hl
        active['logfiles'] = bl

        return active


    # ======================================================================
    #  GET /api/loggers
    #
    def read(self, id=None):
        """
        Handle GET requests for loggers API
        """
        self.logger.info(f"LoggersController.read('{id}')")

        config = self.load_logging_config()
        loggers = config['loggers']
        loggers['root'] = config['root']
        loggers['root']['active'] = self.get_logger_active_configuration()

        loggerlist = self.get_active_loggers()
        self.logger.info("loggerlist = {}".format(loggerlist))

        for logger in loggerlist:
            if loggers.get(logger, None) == None:
                # self.logger.info("active but not configured logger = {}".format(logger))
                loggers[logger] = {}
                loggers[logger]['not_conf'] = True

            loggers[logger]['active'] = self.get_logger_active_configuration(logger)

        self.logger.info("read: logger = {} -> {}".format(logger, loggers[logger]))

        self.logger.info("read: loggers = {}".format(loggers))

        response = {}
        response['loggers'] = loggers
        response['active_plugins'] = self._sh.plugins.get_loaded_plugins()
        response['active_logics'] = self._sh.logics.get_loaded_logics()
        return json.dumps(response)

    read.expose_resource = True
    read.authentication_needed = False


    def update(self, id=None, level=None):
        """
        Handle PUT requests for loggers API
        """
        self.logger.info(f"LoggersController.update('{id}'), level='{level}'")

        if self.set_active_logger_level(id, level):
            response = {'result': 'ok'}
        else:
            response = {'result': 'error', 'description': 'unable to set logger level'}

        return json.dumps(response)

    update.expose_resource = True
    update.authentication_needed = True


    def add(self, id=None, level=None):
        """
        Handle DELETE requests for loggers API
        """
        self.logger.info(f"LoggersController.add('{id}', level='{level}'")

        response = {'result': 'ok', 'description': ''}
        # add logger to active loggers
        lg = logging.getLogger(id)
        lg.setLevel(lg.parent.level)

        # add logger definition to logging.yaml
        self.load_logging_config_for_edit()
        self.logging_config['loggers'][id] = {'level': default_level}
        self.save_logging_config(create_backup=True)

        self.logger.notice(f"Logger '{id}' added")

        return json.dumps(response)

    add.expose_resource = True
    add.authentication_needed = True


    def delete(self, id=None, level=None):
        """
        Handle DELETE requests for loggers API
        """
        self.logger.info("LoggersController.delete('{}', level='{}'".format(id, level))

        response = {'result': 'ok', 'description': ''}
        # delete active logger
        active_logger = logging.root.manager.loggerDict.get(id, None)
        if active_logger is None:
             response = {'result': 'error', 'description': 'active logger not found'}
        else:
            active_logger.setLevel(active_logger.parent.level)
            for hdlr in active_logger.handlers:
                active_logger.removeHandler(hdlr)

        # delete logger definition from logging.yaml
        self.load_logging_config_for_edit()
        del self.logging_config['loggers'][id]
        self.save_logging_config(create_backup=True)

        self.logger.notice(f"Logger '{id}' removed")

        return json.dumps(response)

    delete.expose_resource = True
    delete.authentication_needed = True

