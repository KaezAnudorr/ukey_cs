"""原生桌面样例：点击登录才开始设备认证，不打开浏览器。"""
import queue
import threading
import tkinter as tk
from tkinter import ttk

from adapters import LoginError


class Desktop:
    def __init__(self, runtime):
        self.runtime = runtime
        self.flow = runtime.workflow
        self.root = tk.Tk()
        self.root.title('C/S UKey 登录实验 | ' + ('全模拟' if runtime.mode == 'mock' else '真实接口适配'))
        self.root.geometry('780x570')
        self.root.minsize(740, 540)
        self.events = queue.Queue()
        self.attempt = None
        self.worker = None
        self.password = ''
        self.pin_window = None
        style = ttk.Style(self.root)
        style.theme_use('clam')
        style.configure('.', font=('Microsoft YaHei UI', 11))
        style.configure('TFrame', background='#F4F6FA')
        style.configure('TLabel', background='#F4F6FA', foreground='#23344D')
        style.configure('Title.TLabel', font=('Microsoft YaHei UI', 23, 'bold'))
        style.configure('State.TLabel', foreground='#205CA8')
        style.configure('Primary.TButton', background='#205CA8', foreground='white', padding=(20, 10))
        style.map('Primary.TButton', background=[('active', '#16457F'), ('disabled', '#75869E')])
        body = ttk.Frame(self.root, padding=32)
        body.pack(fill='both', expand=True)
        ttk.Label(body, text='业务登录', style='Title.TLabel').pack(anchor='w')
        mode_text = ('全模拟实验 · 不调用真实 UKey，不连接管理平台' if runtime.mode == 'mock'
                     else '真实助手 + NMR · 业务仍是本机样例，不是现网系统')
        ttk.Label(body, text=mode_text, style='State.TLabel').pack(anchor='w', pady=(8, 24))
        form = ttk.Frame(body)
        form.pack(fill='x')
        form.columnconfigure(1, weight=1)
        ttk.Label(form, text='业务账号').grid(row=0, column=0, sticky='w', padx=(0, 20), pady=8)
        self.username = ttk.Entry(form, width=36)
        self.username.grid(row=0, column=1, sticky='ew')
        self.username.insert(0, 'alice')
        ttk.Label(form, text='业务密码').grid(row=1, column=0, sticky='w', pady=8)
        self.password_entry = ttk.Entry(form, show='●')
        self.password_entry.grid(row=1, column=1, sticky='ew')
        self.password_entry.insert(0, 'demo-password')
        ttk.Label(body, text='本机样例业务：alice / demo-password；原业务仍负责校验密码。').pack(anchor='w', pady=(8, 18))
        self.login_button = ttk.Button(body, text='登录并验证 UKey', style='Primary.TButton', command=self.begin)
        self.login_button.pack(anchor='w')
        ttk.Separator(body).pack(fill='x', pady=24)
        self.status = tk.StringVar(value='等待登录。点击按钮后才触发安全认证。')
        ttk.Label(body, textvariable=self.status, wraplength=690).pack(anchor='w')
        self.steps = tk.StringVar(value='待执行：读取设备 → PIN 与签名 → 服务端验签 → 业务登录')
        ttk.Label(body, textvariable=self.steps, wraplength=690, style='State.TLabel').pack(anchor='w', pady=(12, 0))
        ttk.Label(body, text='应用：' + runtime.app_id).pack(anchor='w', side='bottom')
        self.root.protocol('WM_DELETE_WINDOW', self.close)
        self.root.after(60, self.poll)

    def background(self, kind, function):
        def job():
            try:
                self.events.put((kind, function()))
            except (LoginError, OSError, ValueError) as error:
                self.events.put(('error', str(error)))
        self.worker = threading.Thread(target=job, daemon=True)
        self.worker.start()

    def begin(self):
        username = self.username.get().strip()
        if not username or not self.password_entry.get():
            self.status.set('请填写业务账号和密码。')
            return
        self.password = self.password_entry.get()
        self.login_button.state(['disabled'])
        self.username.state(['disabled'])
        self.password_entry.state(['disabled'])
        self.status.set('读取设备并获取本次登录挑战；尚未向业务系统提交账号密码。')
        self.background('prepared', lambda: self.flow.prepare(username))

    def show_pin(self, attempt):
        self.attempt = attempt
        self.status.set('业务登录已暂停，等待安全认证。')
        self.steps.set('已读取设备和挑战 → 等待 PIN → 待验签 → 未提交业务登录')
        window = tk.Toplevel(self.root)
        self.pin_window = window
        window.title('UKey 安全认证')
        x = self.root.winfo_rootx() + (self.root.winfo_width() - 500) // 2
        y = self.root.winfo_rooty() + (self.root.winfo_height() - 350) // 2
        window.geometry(f'500x350+{max(0, x)}+{max(0, y)}')
        window.resizable(False, False)
        window.transient(self.root)
        window.grab_set()
        panel = ttk.Frame(window, padding=28)
        panel.pack(fill='both', expand=True)
        ttk.Label(panel, text='验证后继续本次登录', font=('Microsoft YaHei UI', 17, 'bold')).pack(anchor='w')
        ttk.Label(panel, text='业务账号：' + attempt['username']).pack(anchor='w', pady=(14, 4))
        ttk.Label(panel, text='模拟设备' if self.runtime.mode == 'mock' else '已识别真实设备（不显示序列号）').pack(anchor='w')
        ttk.Label(panel, text='仅模拟 PIN：123456' if self.runtime.mode == 'mock' else '请输入设备 PIN；错误后不会自动重试。', style='State.TLabel').pack(anchor='w', pady=(12, 6))
        pin = ttk.Entry(panel, show='●', width=32)
        pin.pack(fill='x')
        pin.focus_set()
        buttons = ttk.Frame(panel)
        buttons.pack(fill='x', pady=(22, 0))

        def cancel():
            pin.delete(0, 'end')
            window.destroy()
            self.pin_window = None
            self.background('cancelled', lambda: self.flow.finish(attempt, None, self.password))

        def submit():
            value = pin.get()
            if not value:
                return
            pin.delete(0, 'end')
            window.destroy()
            self.pin_window = None
            self.status.set('正在验证 PIN、签名与服务端验签；全部通过才提交业务登录。')
            self.background('finished', lambda: self.flow.finish(attempt, value, self.password))

        ttk.Button(buttons, text='取消本次登录', command=cancel).pack(side='left')
        ttk.Button(buttons, text='验证并继续', style='Primary.TButton', command=submit).pack(side='right')
        window.protocol('WM_DELETE_WINDOW', cancel)
        window.bind('<Escape>', lambda _: cancel())
        window.bind('<Return>', lambda _: submit())

    def reset(self):
        self.password = ''
        self.attempt = None
        self.login_button.state(['!disabled'])
        self.username.state(['!disabled'])
        self.password_entry.state(['!disabled'])

    def poll(self):
        try:
            kind, result = self.events.get_nowait()
        except queue.Empty:
            pass
        else:
            if kind == 'prepared':
                self.show_pin(result)
            elif kind == 'finished':
                self.status.set('登录成功：' + result['user'] + '。认证通过后才执行了原业务密码校验。')
                self.steps.set('设备已读取 → PIN 与签名通过 → 服务端验签通过 → 业务登录成功')
                self.reset()
            elif kind == 'cancelled':
                self.status.set('已取消本次登录，没有向业务系统提交账号密码。')
                self.steps.set('本次挑战已撤销；重新点击登录将生成新挑战。')
                self.reset()
            else:
                self.status.set('登录已停止：' + result)
                self.steps.set('不会绕过认证，也不会自动改用模拟模式。')
                self.reset()
        self.root.after(60, self.poll)

    def close(self):
        # 已点击“验证并继续”后的网络事务允许完成，避免窗口关闭造成状态误判。
        if self.worker and self.worker.is_alive():
            self.status.set('正在处理本次请求，请等待结果后关闭。')
            return
        if self.attempt:
            try:
                self.flow.cancel(self.attempt)
            except LoginError:
                pass  # 服务端仍按期限失效；不提交业务登录。
        self.root.destroy()

    def run(self):
        self.root.mainloop()
