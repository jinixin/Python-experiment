1. 概述

   1. raft是一种分布式共识协议, raft解决的是多个节点如何达成共识的问题
   1. raft保证了高可用, 但不是强一致, 而是最终一致性
   1. raft把时间分成了一个个任期, 任期总是以选举开始的, 如果选举失败, 该任期会立即结束
   1. 在大多数节点挂掉后,  因无法选出leader, 集群就不能对外提供服务了
   1. 共识算法一般基于复制状态机, 即相同的初始状态 + 相同的输入 = 相同的结束状态. raft通过日志复制与复制状态机实现共识
   1. 应用: 上层模块将指令发给raft层, raft层作为共识模块, 达成共识后, 将达成共识的指令返回上层模块. 比如Etcd, TiKV等

2. 节点

   1. 节点类型
      1. 一个节点任一时刻, 可能有五个状态: leader, follower, candidate, learner, pre-candidate
      2. learner: 新加入的节点, 不具备投票权, 需要从leader那同步完数据才能变为follower
      3. pre-candidate: follower转为candidate的中间态. 发起pre-vote投票, 当超过半数节点响应后才能转为candidate发起选举, 否则退回follower
   2. 节点状态
      1. 每一个节点都有的持久化状态
         1. term: 当前任期号
         2. votedFor: 当前任期给哪个节点投了票
         3. log[]: 已经提交的日志
      2. 每一个节点都有的非持久化状态
         1. commitIndex: 最大的已被提交的日志条目的有序编号
         2. lastApplied: 最大的已被应用到状态机的日志条目的有序编号
         3. lastApplied一般小于commitIndex, 因为日志只有在提交后, 才能被应用到状态机
      3. leader独有的非持久化状态
         1. nextIndex[]: 应该发送给每一个follower的下一个日志条目的有序编号. leader当选时, 全置为leader当前日志条目的有序编号+1, follower拒绝了再回溯
         2. matchIndex[]: 已经同步到每一个follower的日志条目的有序编号

3. 领导人选举

   1. follower变为leader

      所有节点启动时都是follower, 一段时间内未收到来自leader的心跳, 就从follower切换到candidate发起选举. 当candidate收到集群中过半节点的选票, 就会变为leader. 当集群总共有n个节点, 过半节点数量为n/2+1

   2. leader变为follower

      1. leader如果发现心跳响应中其他机器term比自己大, 就自动切换为follower
      2. 如果leader在选举超时时间内无法向过半节点完成心跳, 该leader会退回follower, 并对客户端请求都返回失败

   3. 选举过程

      1. 增加当前节点的term号, 并将节点从follower切换为candidate

      2. 重置选举超时计时器

         candidate发起选举后, 都会记录一个选举超时, 该时间在150ms至300ms之间随机, 一旦超时但仍未完成选举, 就增加当前节点的term, 并开启新一轮选举

      3. 投自己一票, 给其他节点并发发送RequestVote的RPC请求

         1. def RequestVote RPC(term, candidateId, lastLogIndex, lastLogTerm, isPreVote):

            ​	return term, voteGranted

         2. 请求参数

            1. term: 当前candidate的term
            2. lastLogIndex: 当前节点最后一条已提交日志条目的有序编号
            3. lastLogTerm: 当前节点最后一条已提交日志条目的任期号
            4. isPreVote: 该请求是预投票, 还是选主投票

         3. 响应字段

            1. term: 被请求节点的当前任期号
            2. voteGranted: 被请求节点是否同意投票给当前candidate

      4. 在被请求节点看来, 必须同时满足以下两条件, 被请求节点才会同意投票给这个拉票的节点

         1. 当前任期内, 被请求节点还没有投票
         2. 拉票节点掌握的信息不能比被请求节点知道的少

      5. 等待其他节点的回复, 选举拉票的三种结果

         1. 收到过半节点的投票, 则赢得选举, candidate成为leader

         2. 被告知其他节点已当选, candidate自行成为follower

         3. 未收到过半节点的投票, 保持candidate状态, 选举超时后重新发出选举

            两个candidate同时竞选, 一节点发现请求对方选票响应中的term不低于自己的term, 就知道有leader或对方开启新一轮选举, 自动转化为follower

      6. candidate一旦成为leader, leader会给所有节点发送心跳消息, follower收到心跳后, 会重置自己的选举耗时. 当选举耗时超过选举超时时间, 就会引发选举

4. 日志复制

   2. 日志

      1. 日志是由日志条目组成的数组, 每个日志条目由"日志条目的有序编号+日志条目创建时的任期号+命令"构成
      2. 如果不同节点的日志中两个条目有相同的有序编号和任期号, 则它们存储的命令是一样的, 且存储的之前所有日志条目都是一样的

   3. 执行命令的过程 (类似于二阶段提交)

      1. 客户端向leader发送请求

      2. leader将该请求存储在日志中, 并在下一次心跳时将新日志条目同步到所有follower.

         同步时leader会把新日志条目紧挨的上一次已同步日志条目的有序编号和任期号也带上. follower只有在本地日志中找到对应的日志条目, 才会接受新日志条目, 否则会拒绝, 而leader会单独为这台follower不断向前回溯, 直到找到双方共识点, 然后用leader的日志覆盖follower共识点后的日志

      3. leader等待大多数follower的日志持久化回应. 没有回应的follower, leader会不停重新同步

      4. leader收到过半节点的持久化回应后, leader会将该日志条目应用到状态机, 即提交该日志条目, 并通知所有follower该日志条目已被提交

   4. AppendEntriesRPC请求

      1. def AppendEntries RPC(term, leaderId, prevLogIndex, prevLogTerm, entries[], leaderComit):

         ​	return term, success

      2. 请求参数

         1. term: leader当前的任期号
         2. leaderId: leader当前的节点ID
         3. prevLogIndex: 前一块已同步日志条目的有序编号
         4. prevLogTerm: 前一块已同步日志条目的任期号
         5. entries[]: 给follower发送的日志条目, 一次可以批量多个. 作为心跳时该项可缺省
         6. leaderCommit: 当前leader提交日志条目的有序编号, follower收到后会将对应的日志条目用于自己的状态机

      3. 响应字段

         1. term: 响应节点的任期号

   5. 日志压缩

      1. 日志无限增长, 会导致空间消耗且节点重启时回放时间过长, 故引入快照
      2. 每个节点都单独做快照, 且只能对已提交的日志做快照, 快照前的日志会被丢弃
      3. 快照包含"节点数据的当前状态"和"最后一条已提交的日志条目的有序编号和任期", 后者用于日志同步时进行检查
      4. 当有新节点加入或节点落后太多时, leader会将快照发给follower

5. 成员变更

   1. 脑裂: 一个集群原本有一个主节点被看作大脑. 由于网络不稳定, 集群被分隔为多个部分, 每个部分都产生了自己的主节点, 就可以被称为脑裂
   2. 不停机的情况下, raft集群动态添加/删除群成员, 有以下两种方式:
      1. 单节点变更
      2. 多节点变更
   3. 单节点变更, 可以保证不会出现脑裂, 以下为几种情况分析:
      1. 原有3台, 新增1台. 原有的过半节点数是2, 现有的过半节点数是3
      2. 原有4台, 新增1台, 原有的过半节点数是3, 现有的过半节点数是3
      3. 原有4台, 减少1台, 原有的过半节点数是3, 现有的过半节点数是2
      4. 原有5台, 减少1台, 原有的过半节点数是3, 现有的过半节点数是3
      5. 可以看到, 一台一台增加/增减, 不会出现选出两个leader的可能

6. 预投票

   1. 目脱离集群的机器, 会不断发起选举, 从而造成自身的term很大. 当该节点重新加入集群后, 其的高term将导致leader退位, 影响集群的正常运行
   2. 引入预投票(pre-vote), 即选主时, follower先转为pre-candidate, pre-candidate向所有节点拉票要求参与竞选. pre-candidate必须获得过半节点的赞同, 然后才能转为candidate, 增加自己任期号, 以及之后的向所有节点拉票
   3. 一个节点满足以下条件, 才会赞同pre-candidate:
      1. 该pre-candidate日志很新
      2. 当前节点已和leader失联

7. 安全性

   1. 只有拥有最新的已提交日志条目的follower才能成为leader. 拉票时, 同时会上传最新日志条目的有序编号和任期号. 若拉票节点的最新一次记录小于本节点, 本节点是不会将票发给求票节点
   2. leader不会覆盖自己的日志, follower严格复制leader的日志, 必要时强行覆盖
   3. leader只能提交当前任期的日志, 不能对老任期的日志做覆盖

参考自:

http://thesecretlivesofdata.com/raft/
		http://tanxinyu.me/raft/#AppendEntriesRPC
		https://qeesung.github.io/2020/05/31/Raft-集群成员变更.html

