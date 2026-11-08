# Linux：共享内存、消息队列与线程

> 上周把「管道」这条线走通（匿名 pipe + 双 FIFO），这周往两头扩：一头是**零拷贝的共享内存**、一头是**带边界的消息队列**，再往下是**同一进程内的并发**——线程。
> 三条线其实在回答同一个问题：**数据和执行流怎么跨边界传递，代价是什么。**

## 一、共享内存：四步把一块内存挂到两个进程

共享内存是几种 IPC 里**最快**的一种，因为它**零拷贝**——数据只写一次，两个进程读的是同一块物理页。

```c
// ① 打开/创建一个 POSIX 共享内存对象，拿到 fd
int fd = shm_open("/letter", O_CREAT | O_RDWR, 0644);

// ② 决定它多大（新建时为 0，必须显式撑开）
ftruncate(fd, 100);

// ③ 映射到本进程地址空间
char *share = mmap(NULL, 100, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);

// ④ 当普通指针用；收尾
munmap(share, 100);
shm_unlink("/letter");      // 注意：只删名字，已映射的进程仍能用
```

### 四个容易错的点

| 点 | 说明 |
| --- | --- |
| 忘了 `ftruncate` | 新建的 shm 对象大小为 0，直接 `mmap` 再写会 SIGBUS |
| `MAP_SHARED` 写成 `MAP_PRIVATE` | 后者只得到**私有副本**，写完对方看不到，看起来「共享内存没生效」 |
| 判断映射失败用 `== NULL` | `mmap` 失败返回 **`MAP_FAILED`**（即 `(void*)-1`），不是 `NULL` |
| 以为共享内存自带同步 | 它只共享内存，**不带任何互斥**：谁先写谁后读必须自己配信号量 |

### 同步一定要自己配

共享内存最典型的用法是配一个 POSIX 具名信号量：

```c
sem_t *sem = sem_open("/s", O_CREAT, 0644, 0);   // 初值 0

// 写端
strcpy(share, "hello");
sem_post(sem);                                    // 告诉读端：写完了

// 读端
sem_wait(sem);                                    // 等到有人 post
printf("%s\n", share);

// 收尾
sem_close(sem);
sem_unlink("/s");
```

顺序反过来就是经典 bug：读端在写端 `strcpy` 之前就读，读到一串 `\0`，而且**不报错**——共享内存不会替你检测。

## 二、消息队列：带边界和优先级的信箱

消息队列比共享内存慢，因为**每次收发都是一次内核拷贝**，但它换来了三样共享内存给不了的东西：**消息边界、优先级、阻塞语义**。

```c
struct mq_attr attr;
attr.mq_maxmsg  = 10;     // 队列最多几条
attr.mq_msgsize = 256;    // 单条最大字节

mqd_t mq = mq_open("/mq", O_CREAT | O_RDWR, 0644, &attr);

mq_send(mq, "hi", 3, 5);      // 第 4 个参数是优先级，越大越先被取出
char buf[256];
unsigned prio;
mq_receive(mq, buf, sizeof(buf), &prio);   // 总是取当前优先级最高的那条

mq_close(mq);
mq_unlink("/mq");
```

- **默认阻塞**：队列空时 `mq_receive` 会挂住；`mq_open` 时加 `O_NONBLOCK`，没消息就直接返回 `EAGAIN`。
- **有边界**：`mq_maxmsg` / `mq_msgsize` 写死在 attr 里，超了 `mq_send` 会失败（阻塞或 `EAGAIN`），这本身就替你做了一层流控——管道没有这个。

## 三、两者的取舍

| | 共享内存 | 消息队列 |
| --- | --- | --- |
| 拷贝次数 | **0**（零拷贝） | 每次收发 1 次内核拷贝 |
| 速度 | 最快 | 慢于共享内存 |
| 消息边界 | 无，自己定协议 | **有**，天然按条 |
| 优先级 | 无 | **有** |
| 同步 | **全自己写** | 内核帮你处理了生产者/消费者 |
| 适合 | 数据量大、同步能自己管住（大块图像、共享缓冲区） | 控制消息、任务分发、需要优先级（日志、任务队列） |

一句取舍：**数据量大、同步自己管得住 → 共享内存；要边界、要优先级、不想写同步 → 消息队列。**

## 四、线程：创建只要一个调用，收尾有三种走法

```c
void *routine(void *arg) {          // 入参和返回值都只能是 void*
    int *r = malloc(sizeof(int));   // 返回值不能指向线程栈！
    *r = 42;
    return r;
}

pthread_t tid;                       // unsigned long，用来标识线程
int ret = pthread_create(&tid, NULL, routine, NULL);   // 返回 0 才是成功
```

- 多个参数 / 多个返回值：自己打包成 `struct`，用指针传。
- `attr` 传 `NULL` 就是默认属性（栈大小、优先级都不用管）。
- 编译必须加 **`-pthread`**，否则链接不到线程库。

### 终止的三条路

| 方式 | 谁来结束 | 收尾 |
| --- | --- | --- |
| 线程函数 `return` / `pthread_exit(retval)` | 自己 | 需要别人 `join` 才回收资源 |
| `pthread_cancel(tid)` | 别人发起 | **只是请求**，真正退出要跑到取消点（`read`、`sleep` 等） |
| `pthread_detach(tid)` | —— | 结束后自动回收，**但不能再 join** |

```c
void *retval;
pthread_join(tid, &retval);          // 等它结束、取返回值、回收资源
if (retval == PTHREAD_CANCELED)      // 被 cancel 掉的线程，join 回来是这个值
    puts("线程被取消了");
else
    printf("线程返回 %d\n", *(int*)retval);
```

### 两个必须记住的点

1. **要么 `join`、要么 `detach`**，否则线程结束了资源不回收——和僵尸进程一个道理（僵尸进程是「退出但没被 wait」，这里是「退出但没被 join」）。
2. **`pthread_cancel` 只是发请求，不是命令**。默认是 deferred 模式，线程要跑到取消点才真正退出；唯一可靠的判断方式是看 `join` 回来的是不是 `PTHREAD_CANCELED`。

## 五、一条线串起来

```
管道（亲缘进程，半双工，字节流）
  └─ FIFO（无亲缘，双 FIFO 才能全双工）
       └─ 共享内存（零拷贝，但同步全自己写）
       └─ 消息队列（有边界、有优先级，内核管同步）
线程（同进程内，共享地址空间 → 共享内存的「极端情形」：连映射都不用，但竞争也最激烈）
```

有意思的是这条演进线的规律：**越往下越快，内核替你做的事越少，你要自己保证的约束越多。** 共享内存快，是因为它把「同步」这个最难的活全推给了你；线程更快，是因为连「进程边界」都省了，于是所有数据竞争都直接暴露在同一块地址空间里——下周的线程同步（互斥锁、条件变量、信号量）就是在补这一课。

## 待做

- [ ] 三个 demo（shm / mq / pthread）整理成可复现仓库，每个带 Makefile 和运行说明
- [ ] 共享内存版加环形缓冲区 + 双信号量（empty/full），做成生产者-消费者
- [ ] 线程 demo 加一个「不 join 也不 detach」的对照，用 `ps -L` 观察资源不回收
