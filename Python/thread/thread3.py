#!/usr/bin/env python
# coding=utf-8

import time
import threading


class MyThread(threading.Thread):
    def __init__(self, func, args):
        threading.Thread.__init__(self)
        self.func = func
        self.args = args

    def run(self):
        self.func(*self.args)


def target_func(index, time_sleep):
    print 'start %d' % index
    time.sleep(time_sleep)
    print 'end %d, consume %d seconds' % (index, time_sleep)


def main_task():
    start = time.time()
    thread_list, time_list = [], [2, 4, 6]
    for index, time_sleep in enumerate(time_list):
        thread = MyThread(target_func, (index, time_sleep))
        thread_list.append(thread)
    for thread in thread_list:
        thread.start()
    for thread in thread_list:
        thread.join()
    print 'origin need %d seconds, now only need %d seconds' % (
        reduce(lambda x, y: x + y, time_list, 0), int(time.time() - start))


if __name__ == '__main__':
    main_task()
