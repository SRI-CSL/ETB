""" ETB utility functions

..
   Copyright (C) 2013 SRI International

   This program is free software: you can redistribute it
   and/or modify it under the terms of the GNU General Public License as
   published by the Free Software Foundation, either version 3 of the
   License, or (at your option) any later version. This program is
   distributed in the hope that it will be useful, but WITHOUT ANY
   WARRANTY; without even the implied warranty of MERCHANTABILITY or
   FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License
   for more details.  You should have received a copy of the GNU General
   Public License along with this program.  If not, see
   <http://www.gnu.org/licenses/>.
"""

import logging
import json
import copy
import threading
import traceback
import weakref
from queue import Queue, Empty

def flatten(l, ltypes=(list, tuple)):
    ltype = type(l)
    l = list(l)
    i = 0
    while i < len(l):
        while isinstance(l[i], ltypes):
            if not l[i]:
                l.pop(i)
                i -= 1
                break
            else:
                l[i:i + 1] = l[i]
        i += 1
    return ltype(l)

class CronJob(object):
    """object that will spawn a bunch of tasks regularly
    """
    def __init__(self, etb, period):
        threading.Timer.__init__(self, period, self.run)
        self.etb = etb
        self.period = period
        self.onIteration = Slot()  # signal(etb) at every iteration
        self.schedule_next_iteration()
        self._time = None
        self._stop = False

    def schedule_next_iteration(self):
        timer = threading.Timer(self.period, self.run)
        timer.daemon = True
        timer.start()
        self._timer = timer

    def stop(self):
        """Stops the cron object"""
        self._stop = True
        if self._timer:
            self._timer.cancel()

    def run(self):
        """Run all tasks, and schedule next iteration"""
        if self._stop:
            return
        # run again in period
        self.schedule_next_iteration()
        # do my job
        self.onIteration.signal(self.etb)


class ThreadPool(object):
    "A pool of threads"

    def __init__(self, etb, num=50, debug=False):
        "initialize with given number of threads and etb instance"
        self.num = num
        self.etb = etb
        self._stop = False
        self.logger = self.etb.log
        self.debug = debug
        self.queue = Queue()
        self.current_tasks = set(())  # TODO remove this, too brittle and complex
        self._rlock = threading.RLock()
        # actual pool of threads
        self.threads = [threading.Thread(target=self._worker_fun) for i in range(num)]
        for i in range(num):
            self.threads[i].daemon = True
            self.threads[i].start()

    def _worker_fun(self):
        "function to be run by threads in thread pool"
        while not self._stop:
            try:
                task = self.queue.get(timeout=2)
            except Empty:
                task = None
            if task:
                self._process_task(task)
                self.queue.task_done()
            
    def _process_task(self, task):
        "process this task, safely."
        if self.debug:
            self.logger.debug('Processing %s' % task)
        try:
            task(self.etb)
        except Exception as e:
            self.logger.warning('error while processing task %s: %s', task, e)
            traceback.print_exc()
        finally:  # be sure to remove the task from the list of current tasks
            with self._rlock:
                self.current_tasks.remove(task)

    def schedule(self, task):
        "schedule the task to be run by a thread"
        with self._rlock:
            self.current_tasks.add(task)
        self.queue.put(task)

    def stop(self, wait=False):
        """ask threads to stop, but do not wait for them to terminate,
        unless [wait] is True."""
        self._stop = True
        if wait:
            for t in self.threads:
                t.join()


class Slot(object):
    """Component used to attach handlers. Each time the slot.signal()
    is called with some parameters, all attached handlers are called 
    sequentially with this parameter.

    >>> s = Slot()
    >>> a = 0
    >>> def f(x):
    ...   global a
    ...   a += x
    >>> s.add_handler(f)
    >>> s.signal(42)
    >>> a
    42
    >>> s.add_handler(f)
    >>> s.signal(1)
    >>> a
    44
    """
    def __init__(self):
        self._rlock = threading.RLock()
        self.handlers = weakref.WeakSet()

    def add_handler(self, handler):
        """Add the handler to this slot. The handler will be
        called at each signal() call.
        """
        with self._rlock:
            self.handlers.add(handler)

    def signal(self, arg):
        """call all handlers with arg"""
        with self._rlock:
            # copy handler, to avoid race conditions
            handlers = list(self.handlers)
        for h in handlers:
            try:
                h(arg)
            except Exception as e:
                pass
