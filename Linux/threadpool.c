/* threadpool.c
 * 手写线程池，单文件实现
 * 编译: gcc -pthread threadpool.c -o threadpool
 * 运行: ./threadpool
 *
 * 语义对应 GLib g_thread_pool_free 的 immediate / wait_ 两个参数：
 *   immediate=1: 丢弃队列中未处理的任务
 *   immediate=0: 让 worker 处理完队列中的任务
 *   wait_=1:     阻塞到所有该处理的任务完成才返回
 *   wait_=0:     立即返回，后台清理
 *
 * 硬保证：正在执行的任务永远不会被打断。
 */

#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <pthread.h>
#include <unistd.h>
#include <errno.h>

/* ============================================================
 * 任务定义
 * ============================================================ */
typedef struct task {
    void (*func)(void *);       /* 任务函数 */
    void *arg;                  /* 任务参数 */
    void (*destroy)(void *);    /* 可选：参数销毁函数，丢弃任务时调用 */
    struct task *next;
} task_t;

/* ============================================================
 * 线程池定义
 * ============================================================ */
struct threadpool {
    pthread_mutex_t lock;
    pthread_cond_t  cond;       /* 有任务或关闭时唤醒 worker */
    task_t *head, *tail;
    int count;                  /* 队列中任务数（调试用） */

    pthread_t *threads;
    int nthreads;

    int shutdown;               /* 1 = 不再接受新任务 */
};

typedef struct threadpool threadpool_t;

/* ============================================================
 * worker 主循环
 *
 * 关键点：
 *   - while 防虚假唤醒
 *   - 取任务后解锁再执行，避免串行化
 *   - 只有取任务时检查 shutdown，执行中的任务不被打断
 * ============================================================ */
static void *worker(void *arg)
{
    threadpool_t *pool = (threadpool_t *)arg;

    for (;;) {
        pthread_mutex_lock(&pool->lock);

        /* 队列空且未关闭时睡眠；while 防虚假唤醒 */
        while (pool->head == NULL && !pool->shutdown)
            pthread_cond_wait(&pool->cond, &pool->lock);

        /* 队列空 + 已关闭 → 退出循环 */
        if (pool->head == NULL && pool->shutdown) {
            pthread_mutex_unlock(&pool->lock);
            break;
        }

        /* 取出一个任务 */
        task_t *t = pool->head;
        pool->head = t->next;
        if (pool->head == NULL)
            pool->tail = NULL;
        pool->count--;

        pthread_mutex_unlock(&pool->lock);   /* 解锁后再执行 */

        /* 执行任务（锁外） */
        t->func(t->arg);
        if (t->destroy)
            t->destroy(t->arg);
        free(t);
    }
    return NULL;
}

/* ============================================================
 * 创建线程池
 * 返回池指针，失败返回 NULL
 * ============================================================ */
threadpool_t *threadpool_create(int nthreads)
{
    if (nthreads <= 0)
        nthreads = 1;

    threadpool_t *pool = calloc(1, sizeof(*pool));
    if (!pool)
        return NULL;

    pool->nthreads = nthreads;
    pool->threads = calloc((size_t)nthreads, sizeof(pthread_t));
    if (!pool->threads) {
        free(pool);
        return NULL;
    }

    if (pthread_mutex_init(&pool->lock, NULL) != 0) {
        free(pool->threads);
        free(pool);
        return NULL;
    }
    if (pthread_cond_init(&pool->cond, NULL) != 0) {
        pthread_mutex_destroy(&pool->lock);
        free(pool->threads);
        free(pool);
        return NULL;
    }

    for (int i = 0; i < nthreads; i++) {
        if (pthread_create(&pool->threads[i], NULL, worker, pool) != 0) {
            /* 回滚已创建的线程 */
            pthread_mutex_lock(&pool->lock);
            pool->shutdown = 1;
            pthread_cond_broadcast(&pool->cond);
            pthread_mutex_unlock(&pool->lock);

            for (int j = 0; j < i; j++)
                pthread_join(pool->threads[j], NULL);

            /* 释放队列中的任务 */
            task_t *t = pool->head;
            while (t) {
                task_t *next = t->next;
                if (t->destroy) t->destroy(t->arg);
                free(t);
                t = next;
            }

            pthread_mutex_destroy(&pool->lock);
            pthread_cond_destroy(&pool->cond);
            free(pool->threads);
            free(pool);
            return NULL;
        }
    }
    return pool;
}

/* ============================================================
 * 提交任务
 * 成功返回 0；池已关闭或内存不足返回 -1
 * ============================================================ */
int threadpool_push(threadpool_t *pool,
                    void (*func)(void *),
                    void *arg,
                    void (*destroy)(void *))
{
    if (!pool || !func)
        return -1;

    task_t *t = malloc(sizeof(*t));
    if (!t)
        return -1;
    t->func    = func;
    t->arg     = arg;
    t->destroy = destroy;
    t->next    = NULL;

    pthread_mutex_lock(&pool->lock);
    if (pool->shutdown) {
        pthread_mutex_unlock(&pool->lock);
        free(t);
        return -1;
    }

    if (pool->tail)
        pool->tail->next = t;
    else
        pool->head = t;
    pool->tail = t;
    pool->count++;

    pthread_cond_signal(&pool->cond);   /* 唤醒一个 worker */
    pthread_mutex_unlock(&pool->lock);
    return 0;
}

/* ============================================================
 * 后台清理线程：wait_=0 时使用
 * 负责 join 所有 worker 并释放池
 * ============================================================ */
static void *cleaner(void *arg)
{
    threadpool_t *pool = (threadpool_t *)arg;

    for (int i = 0; i < pool->nthreads; i++)
        pthread_join(pool->threads[i], NULL);

    pthread_mutex_destroy(&pool->lock);
    pthread_cond_destroy(&pool->cond);
    free(pool->threads);
    free(pool);
    return NULL;
}

/* ============================================================
 * 销毁线程池
 *
 * immediate = 1: 丢弃队列中未处理的任务（调用其 destroy）
 * immediate = 0: worker 把队列中任务处理完
 * wait_     = 1: 阻塞到所有该处理的任务完成
 * wait_     = 0: 立即返回，后台 cleaner 释放
 * ============================================================ */
void threadpool_free(threadpool_t *pool, int immediate, int wait_)
{
    if (!pool)
        return;

    pthread_mutex_lock(&pool->lock);
    pool->shutdown = 1;

    if (immediate) {
        /* 丢弃队列中所有未处理任务 */
        task_t *t = pool->head;
        while (t) {
            task_t *next = t->next;
            if (t->destroy)
                t->destroy(t->arg);   /* 释放任务数据 */
            free(t);
            t = next;
        }
        pool->head = pool->tail = NULL;
        pool->count = 0;
    }

    /* 广播唤醒所有 worker */
    pthread_cond_broadcast(&pool->cond);
    pthread_mutex_unlock(&pool->lock);

    if (wait_) {
        /* 同步清理 */
        for (int i = 0; i < pool->nthreads; i++)
            pthread_join(pool->threads[i], NULL);

        pthread_mutex_destroy(&pool->lock);
        pthread_cond_destroy(&pool->cond);
        free(pool->threads);
        free(pool);
    } else {
        /* 异步清理：交给 detached cleaner */
        pthread_t tid;
        if (pthread_create(&tid, NULL, cleaner, pool) == 0) {
            pthread_detach(tid);
        } else {
            /* 创建失败，退化为同步清理，避免泄漏 */
            for (int i = 0; i < pool->nthreads; i++)
                pthread_join(pool->threads[i], NULL);
            pthread_mutex_destroy(&pool->lock);
            pthread_cond_destroy(&pool->cond);
            free(pool->threads);
            free(pool);
        }
    }
}

/* ============================================================
 * 测试代码
 * ============================================================ */

static pthread_mutex_t g_print_lock = PTHREAD_MUTEX_INITIALIZER;

typedef struct {
    int id;
    int work_ms;
} job_t;

static void job_run(void *arg)
{
    job_t *j = (job_t *)arg;

    pthread_mutex_lock(&g_print_lock);
    printf("  [task %2d] start on thread %lu (work %d ms)\n",
           j->id, (unsigned long)pthread_self(), j->work_ms);
    pthread_mutex_unlock(&g_print_lock);

    usleep((useconds_t)j->work_ms * 1000);

    pthread_mutex_lock(&g_print_lock);
    printf("  [task %2d] done\n", j->id);
    pthread_mutex_unlock(&g_print_lock);
}

static void job_destroy(void *arg)
{
    job_t *j = (job_t *)arg;
    pthread_mutex_lock(&g_print_lock);
    printf("  [task %2d] discarded\n", j->id);
    pthread_mutex_unlock(&g_print_lock);
    free(j);
}

/* 提交 n 个任务，每个工作 ms 毫秒 */
static threadpool_t *make_pool_with_jobs(int nthreads, int njobs, int work_ms)
{
    threadpool_t *pool = threadpool_create(nthreads);
    if (!pool) {
        fprintf(stderr, "create pool failed\n");
        return NULL;
    }

    for (int i = 0; i < njobs; i++) {
        job_t *j = malloc(sizeof(*j));
        j->id = i;
        j->work_ms = work_ms;
        if (threadpool_push(pool, job_run, j, job_destroy) != 0) {
            fprintf(stderr, "push task %d failed\n", i);
            free(j);
        }
    }
    return pool;
}

static void demo(const char *title, int immediate, int wait_)
{
    printf("\n===== %s (immediate=%d, wait_=%d) =====\n",
           title, immediate, wait_);
    threadpool_t *pool = make_pool_with_jobs(3, 8, 80);
    if (!pool) return;

    usleep(50 * 1000);   /* 让部分任务先跑起来 */
    printf("--> calling threadpool_free\n");
    threadpool_free(pool, immediate, wait_);
    printf("<-- threadpool_free returned\n");
}

int main(void)
{
    printf("CPU cores hint: %ld\n", sysconf(_SC_NPROCESSORS_ONLN));

    /* 1. 安全关闭：所有任务完成才返回 */
    demo("FALSE, TRUE  (safe, wait all)", 0, 1);

    /* 2. 丢弃队列，但等正在运行的完成 */
    demo("TRUE, TRUE   (discard, wait running)", 1, 1);

    /* 3. 不丢任务，但立即返回 */
    demo("FALSE, FALSE (keep tasks, return now)", 0, 0);

    /* 4. 丢弃队列，立即返回 */
    demo("TRUE, FALSE  (discard, return now)", 1, 0);

    printf("\nmain exiting\n");
    return 0;
}
