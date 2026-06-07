from aiogram.fsm.state import State, StatesGroup


class UserSG(StatesGroup):
    charging = State()          # waiting for charge amount
    charge_receipt = State()    # waiting for receipt photo
    support_msg = State()       # waiting for support message text
    gift_code = State()         # waiting for gift code
    discount_code = State()     # waiting for discount code (during purchase)
    custom_volume = State()     # custom service: volume
    custom_days = State()       # custom service: days
    agent_note = State()        # agent request note
    transfer_target = State()   # service transfer: target user id


class AdminSG(StatesGroup):
    broadcast = State()
    user_lookup = State()
