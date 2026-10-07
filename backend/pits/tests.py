"""验收：村场改名只改显示名——不动角色、不清会话、各处同名、并发只留一版。"""

import json
import threading

from django.test import Client, TransactionTestCase

from pits.models import LiquorSample, Pit, User, Yard
from pits.seed import seed_demo


def login(client: Client, username: str, password: str = "123456") -> str:
    resp = client.post(
        "/api/auth/login",
        data=json.dumps({"username": username, "password": password}),
        content_type="application/json",
    )
    assert resp.status_code == 200, resp.content
    return resp.json()["access_token"]


def bearer(token: str) -> dict:
    return {"HTTP_AUTHORIZATION": f"Bearer {token}"}


class RenameYardTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        seed_demo()
        self.admin = Client()
        self.worker = Client()
        self.admin_token = login(self.admin, "admin")
        self.worker_token = login(self.worker, "worker")

    def rename(self, client, token, name):
        return client.post(
            "/api/yard/name",
            data=json.dumps({"name": name}),
            content_type="application/json",
            **bearer(token),
        )

    def test_admin_rename_changes_only_display_name(self):
        resp = self.rename(self.admin, self.admin_token, "北坡鞣场")
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.json()["name"], "北坡鞣场")
        self.assertEqual(Yard.objects.get().name, "北坡鞣场")
        # 只许改显示名：角色一个都不许翻
        self.assertEqual(User.objects.get(username="admin").role, "admin")
        self.assertEqual(User.objects.get(username="worker").role, "worker")

    def test_admin_token_still_alive_after_own_rename(self):
        # 管理员自己提交新名，不得提示未登录
        resp = self.rename(self.admin, self.admin_token, "东溪鞣场")
        self.assertEqual(resp.status_code, 200, resp.content)
        me = self.admin.get("/api/auth/me", **bearer(self.admin_token))
        self.assertEqual(me.status_code, 200, me.content)
        self.assertEqual(me.json(), {"username": "admin", "role": "admin"})

    def test_worker_cannot_rename_and_keeps_worker_session(self):
        resp = self.rename(self.worker, self.worker_token, "黑客鞣场")
        self.assertEqual(resp.status_code, 403, resp.content)
        # 库里场名没动
        self.assertEqual(Yard.objects.get().name, "南冈鞣场")
        # 角色仍是操作工，登录态不断
        self.assertEqual(User.objects.get(username="worker").role, "worker")
        board = self.worker.get("/api/board", **bearer(self.worker_token))
        self.assertEqual(board.status_code, 200, board.content)
        # 工人仍能做工人能做的事：登记酸碱度
        pit = Pit.objects.get(code="东-2")
        sample = self.worker.post(
            f"/api/pits/{pit.id}/samples",
            data=json.dumps({"ph": 4.3}),
            content_type="application/json",
            **bearer(self.worker_token),
        )
        self.assertEqual(sample.status_code, 200, sample.content)
        self.assertEqual(LiquorSample.objects.filter(pit=pit).count(), 1)
        # 工人依旧打不开管理专页：改名再试仍是 403
        self.assertEqual(
            self.rename(self.worker, self.worker_token, "再试一场").status_code, 403
        )

    def test_header_drawer_and_ledger_share_one_new_name(self):
        self.assertEqual(self.rename(self.admin, self.admin_token, "西河鞣场").status_code, 200)
        board = self.admin.get("/api/board", **bearer(self.admin_token)).json()
        # 楣条（<h1>）、流水抬头、抽屉票夹全部取自这一份 board
        self.assertEqual(board["yard"], "西河鞣场")
        self.assertEqual(board["village"], "青皮村")

    def test_blank_name_rejected_without_touching_anything(self):
        resp = self.rename(self.admin, self.admin_token, "   ")
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertEqual(Yard.objects.get().name, "南冈鞣场")
        self.assertEqual(User.objects.get(username="worker").role, "worker")

    def test_two_operators_racing_leave_exactly_one_name(self):
        results = []
        barrier = threading.Barrier(2)

        def submit(name, out):
            client = Client()
            token = login(client, "admin")
            barrier.wait()
            out.append(self.rename(client, token, name).status_code)

        t1 = threading.Thread(target=submit, args=("甲值班场名", results))
        t2 = threading.Thread(target=submit, args=("乙值班场名", results))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        self.assertEqual(sorted(results), [200, 200])
        final = Yard.objects.get().name
        self.assertIn(final, {"甲值班场名", "乙值班场名"})
        self.assertEqual(Yard.objects.count(), 1)
        # 工人登录态不得断，角色仍是操作工
        board = self.worker.get("/api/board", **bearer(self.worker_token))
        self.assertEqual(board.status_code, 200, board.content)
        self.assertEqual(User.objects.get(username="worker").role, "worker")
