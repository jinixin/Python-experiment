#!/usr/bin/env python
# coding=utf-8

import time
import threading


class ThreadFunc(object):
    def __init__(self, func, args):
        self.func = func
        self.args = args

    def __call__(self):
        self.func(*self.args)


def target_func(index, time_sleep):
    print 'start %d' % index  # 开始任务
    time.sleep(time_sleep)  # 睡眠
    print 'end %d, consume %d seconds' % (index, time_sleep)  # 任务结束，打印耗时


def main_task():
    start = time.time()
    thread_list, time_list = [], [2, 4, 6]
    for index, time_sleep in enumerate(time_list):
        thread = threading.Thread(target=ThreadFunc(target_func, (index, time_sleep)))  # 构建线程对象，target为目标实例
        thread_list.append(thread)  # 将线程对象加入线程列表中

    for thread in thread_list:  # 开始每个线程
        thread.start()

    for thread in thread_list:  # 程序挂起，等待所有线程结束
        thread.join()
    print 'origin need %d seconds, now only need %d seconds' % (
        reduce(lambda x, y: x + y, time_list, 0), int(time.time() - start))


if __name__ == '__main__':
    main_task()
