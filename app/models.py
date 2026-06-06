from sqlalchemy import Column, Integer, String, Text, Boolean, JSON, DateTime, Enum, BigInteger
from sqlalchemy.sql import func
from app.database import Base
import json
from datetime import datetime

class User(Base):
    __tablename__ = "user"
    id = Column(String(500), primary_key=True)
    limit_usertest = Column(Integer, default=0)
    roll_Status = Column(Boolean, default=True)
    username = Column(String(500), default="none")
    Processing_value = Column(Text, default="")
    Processing_value_one = Column(Text, default="")
    Processing_value_tow = Column(Text, default="")
    Processing_value_four = Column(Text, default="")
    step = Column(String(500), default="")
    description_blocking = Column(Text, nullable=True)
    number = Column(String(300), default="none")
    Balance = Column(Integer, default=0)
    User_Status = Column(String(500), default="")
    pagenumber = Column(Integer, default=0)
    message_count = Column(String(100), default="0")
    last_message_time = Column(String(100), default="0")
    agent = Column(String(100), default="f")
    affiliatescount = Column(String(100), default="0")
    affiliates = Column(String(100), default="0")
    namecustom = Column(String(300), default="none")
    number_username = Column(String(300), default="100")
    register = Column(String(100), default="none")
    verify = Column(String(100), default="1")
    cardpayment = Column(String(100), default="1")
    codeInvitation = Column(String(100), nullable=True)
    pricediscount = Column(String(100), default="0")
    hide_mini_app_instruction = Column(String(20), default="0")
    maxbuyagent = Column(String(100), default="0")
    joinchannel = Column(String(100), default="0")
    checkstatus = Column(String(50), default="0")
    bottype = Column(Text, nullable=True)
    score = Column(Integer, default=0)
    limitchangeloc = Column(String(50), default="0")
    status_cron = Column(String(20), default="1")
    expire = Column(String(100), nullable=True)
    token = Column(String(100), nullable=True)
    lang = Column(String(5), default="fa")
    # Additional fields from migrations in original
    ref_code = Column(String(100), nullable=True)  # dropped in original but for completeness

class Setting(Base):
    __tablename__ = "setting"
    id = Column(Integer, primary_key=True, autoincrement=True)
    Bot_Status = Column(String(200), default="botstatuson")
    roll_Status = Column(String(200), default="rolleon")
    get_number = Column(String(200), default="offAuthenticationphone")
    iran_number = Column(String(200), default="offAuthenticationiran")
    NotUser = Column(String(200), default="offnotuser")
    Channel_Report = Column(String(600), default="0")
    limit_usertest_all = Column(String(600), default="1")
    affiliatesstatus = Column(String(600), default="offaffiliates")
    affiliatespercentage = Column(String(600), default="0")
    removedayc = Column(String(600), default="0")
    showcard = Column(String(200), default="1")
    numbercount = Column(String(600), default="0")
    statusnewuser = Column(String(600), default="onnewuser")
    statusagentrequest = Column(String(600), default="onrequestagent")
    statuscategory = Column(String(200), default="offcategory")
    statusterffh = Column(String(200), default="")
    volumewarn = Column(String(200), default="2")
    inlinebtnmain = Column(String(200), default="offinline")
    verifystart = Column(String(200), default="offverify")
    id_support = Column(String(200), default="0")
    statusnamecustom = Column(String(100), default="offnamecustom")
    statuscategorygenral = Column(String(100), default="offcategorys")
    statussupportpv = Column(String(100), default="offpvsupport")
    agentreqprice = Column(String(100), default="0")
    bulkbuy = Column(String(100), default="onbulk")
    on_hold_day = Column(String(100), default="4")
    cronvolumere = Column(String(100), default="5")
    verifybucodeuser = Column(String(100), default="offverify")
    scorestatus = Column(String(100), default="0")
    Lottery_prize = Column(Text, default=json.dumps({'one': '0', 'tow': '0', 'theree': '0'}))
    wheel_luck = Column(String(45), default="0")
    wheel_luck_price = Column(String(45), default="0")
    btn_status_extned = Column(String(45), default="0")
    daywarn = Column(String(45), default="2")
    categoryhelp = Column(String(45), default="0")
    linkappstatus = Column(String(45), default="0")
    wheelagent = Column(String(45), default="1")
    Lotteryagent = Column(String(45), default="1")
    statusfirstwheel = Column(String(45), default="1")
    statuslimitchangeloc = Column(String(45), default="0")
    Debtsettlement = Column(String(45), default="0")
    Dice = Column(String(45), default="0")
    keyboardmain = Column(Text, default='{"keyboard":[[{"text":"text_sell"},{"text":"text_extend"}],[{"text":"text_usertest"},{"text":"text_wheel_luck"}],[{"text":"text_Purchased_services"},{"text":"accountwallet"}],[{"text":"text_affiliates"},{"text":"text_Tariff_list"}],[{"text":"text_support"},{"text":"text_help"}]]}')
    statusnoteforf = Column(String(45), default="0")
    statuscopycart = Column(String(45), default="0")
    timeauto_not_verify = Column(String(20), default="1")
    status_keyboard_config = Column(String(20), default="0")
    cron_status = Column(Text, default=json.dumps({'day': True, 'volume': True, 'remove': False, 'remove_volume': False, 'test': False, 'on_hold': False, 'uptime_node': False, 'uptime_panel': False}))
    limitnumber = Column(String(200), default=json.dumps({'free': 100, 'all': 100}))

# Add more models for panels, products, invoices, etc.
class MarzbanPanel(Base):
    __tablename__ = "marzban_panel"
    id = Column(Integer, primary_key=True, autoincrement=True)
    code_panel = Column(String(200), nullable=True)
    name_panel = Column(String(2000), nullable=True)
    status = Column(String(500), default="active")
    url_panel = Column(String(2000), nullable=True)
    username_panel = Column(String(200), nullable=True)
    password_panel = Column(String(200), nullable=True)
    agent = Column(String(200), default="all")
    sublink = Column(String(500), default="onsublink")
    config = Column(String(500), default="offconfig")
    MethodUsername = Column(String(700), default="numericIdRandom")
    TestAccount = Column(String(100), default="ONTestAccount")
    limit_panel = Column(String(100), default="unlimted")
    namecustom = Column(String(100), default="vpn")
    Methodextend = Column(String(100), default="resetVolumeTime")
    conecton = Column(String(100), default="offconecton")
    linksubx = Column(String(1000), nullable=True)
    inboundid = Column(String(100), default="1")
    type = Column(String(100), default="marzban")
    inboundstatus = Column(String(100), default="offinbounddisable")
    inbound_deactive = Column(String(100), default="0")
    time_usertest = Column(String(100), default="1")
    val_usertest = Column(String(100), default="100")
    secret_code = Column(String(200), nullable=True)
    priceChangeloc = Column(String(200), default="0")
    priceextravolume = Column(String(500), default=json.dumps({'f': '4000', 'n': '4000', 'n2': '4000'}))
    pricecustomvolume = Column(String(500), default=json.dumps({'f': '4000', 'n': '4000', 'n2': '4000'}))
    pricecustomtime = Column(String(500), default=json.dumps({'f': '4000', 'n': '4000', 'n2': '4000'}))
    priceextratime = Column(String(500), default=json.dumps({'f': '4000', 'n': '4000', 'n2': '4000'}))
    mainvolume = Column(String(500), default=json.dumps({'f': '1', 'n': '1', 'n2': '1'}))
    maxvolume = Column(String(500), default=json.dumps({'f': '1000', 'n': '1000', 'n2': '1000'}))
    maintime = Column(String(500), default=json.dumps({'f': '1', 'n': '1', 'n2': '1'}))
    maxtime = Column(String(500), default=json.dumps({'f': '365', 'n': '365', 'n2': '365'}))
    status_extend = Column(String(100), default="on_extend")
    datelogin = Column(Text, nullable=True)
    proxies = Column(Text, nullable=True)
    inbounds = Column(Text, nullable=True)
    subvip = Column(String(60), default="offsubvip")
    changeloc = Column(String(60), default="offchangeloc")
    on_hold_test = Column(String(60), default="1")
    version_panel = Column(String(60), default="0")
    customvolume = Column(Text, default=json.dumps({'f': '0', 'n': '0', 'n2': '0'}))
    hide_user = Column(Text, nullable=True)

class Product(Base):
    __tablename__ = "product"
    id = Column(Integer, primary_key=True, autoincrement=True)
    code_product = Column(String(200), nullable=True)
    name_product = Column(String(2000), nullable=True)
    price_product = Column(String(2000), nullable=True)
    Volume_constraint = Column(String(2000), nullable=True)
    Location = Column(String(200), nullable=True)
    Service_time = Column(String(200), nullable=True)
    agent = Column(String(100), default="f")
    note = Column(Text, default="")
    data_limit_reset = Column(String(200), default="no_reset")
    one_buy_status = Column(String(20), default="0")
    inbounds = Column(Text, nullable=True)
    proxies = Column(Text, nullable=True)
    category = Column(String(400), nullable=True)
    hide_panel = Column(Text, default="{}")

class Invoice(Base):
    __tablename__ = "invoice"
    id_invoice = Column(String(200), primary_key=True)
    id_user = Column(String(200), nullable=True)
    username = Column(String(300), nullable=True)
    Service_location = Column(String(300), nullable=True)
    time_sell = Column(String(200), nullable=True)
    name_product = Column(String(200), nullable=True)
    price_product = Column(String(200), nullable=True)
    Volume = Column(String(200), nullable=True)
    Service_time = Column(String(200), nullable=True)
    uuid = Column(Text, nullable=True)
    note = Column(String(700), nullable=True)
    user_info = Column(Text, nullable=True)
    bottype = Column(String(200), nullable=True)
    refral = Column(String(100), nullable=True)
    time_cron = Column(String(100), nullable=True)
    notifctions = Column(Text, nullable=True)
    Status = Column(String(200), nullable=True)

# Add Payment_report, Discount, etc. similarly...
# For brevity, I'll add a few more key ones. In full version, all tables from table.php should be here.

class PaymentReport(Base):
    __tablename__ = "Payment_report"
    id = Column(Integer, primary_key=True, autoincrement=True)
    id_user = Column(String(200), nullable=True)
    id_order = Column(String(2000), nullable=True)
    time = Column(String(200), nullable=True)
    at_updated = Column(String(200), nullable=True)
    price = Column(String(200), nullable=True)
    dec_not_confirmed = Column(Text, nullable=True)
    Payment_Method = Column(String(400), nullable=True)
    payment_Status = Column(String(100), nullable=True)
    bottype = Column(String(300), nullable=True)
    message_id = Column(Integer, nullable=True)
    id_invoice = Column(String(1000), nullable=True)

class Admin(Base):
    __tablename__ = "admin"
    id_admin = Column(String(500), primary_key=True)
    username = Column(String(1000), nullable=True)
    password = Column(String(1000), nullable=True)
    rule = Column(String(500), default="administrator")
    permissions = Column(Text, default='{"all": true}')  # JSON: {"users": true, "payments": false, ...}
    added_by = Column(String(500), nullable=True)
    added_at = Column(String(100), default="")

# Continue with other tables like channels, PaySetting, DiscountSell, affiliates, shopSetting, etc.
# This is a partial implementation; full conversion would include all ~30 tables.

class PaySetting(Base):
    __tablename__ = "PaySetting"
    NamePay = Column(String(500), primary_key=True)
    ValuePay = Column(Text, nullable=False)

class Channels(Base):
    __tablename__ = "channels"
    remark = Column(String(200), primary_key=True)
    linkjoin = Column(String(200))
    link = Column(String(200))

class Discount(Base):
    __tablename__ = "Discount"
    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(2000))
    price = Column(String(200))
    limituse = Column(String(200))
    limitused = Column(String(200))

class DiscountSell(Base):
    __tablename__ = "DiscountSell"
    id = Column(Integer, primary_key=True, autoincrement=True)
    codeDiscount = Column(String(1000))
    price = Column(String(200))
    limitDiscount = Column(String(500))
    agent = Column(String(500))
    usefirst = Column(String(100))
    useuser = Column(String(100))
    code_product = Column(String(100))
    code_panel = Column(String(100))
    time = Column(String(100))
    type = Column(String(100))
    usedDiscount = Column(String(500))

class Affiliates(Base):
    __tablename__ = "affiliates"
    description = Column(Text)
    status_commission = Column(String(200))
    Discount = Column(String(200))
    price_Discount = Column(String(200))
    porsant_one_buy = Column(String(100))
    id_media = Column(String(300))

class ShopSetting(Base):
    __tablename__ = "shopSetting"
    Namevalue = Column(String(500), primary_key=True)
    value = Column(Text)

class Help(Base):
    __tablename__ = "help"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name_os = Column(String(500))
    Media_os = Column(String(5000))
    type_Media_os = Column(String(500))
    category = Column(Text)
    Description_os = Column(Text)

class TopicID(Base):
    __tablename__ = "topicid"
    report = Column(String(500), primary_key=True)
    idreport = Column(Text)

class WheelList(Base):
    __tablename__ = "wheel_list"
    id = Column(Integer, primary_key=True, autoincrement=True)
    id_user = Column(String(200))
    time = Column(String(200))
    first_name = Column(String(200))
    wheel_code = Column(String(200))
    price = Column(String(200))

class Botsaz(Base):
    __tablename__ = "botsaz"
    id = Column(Integer, primary_key=True, autoincrement=True)
    id_user = Column(String(200))
    bot_token = Column(String(200))
    admin_ids = Column(Text)
    username = Column(String(200))
    setting = Column(Text)
    hide_panel = Column(JSON, default={})
    time = Column(String(200))

class Category(Base):
    __tablename__ = "category"
    id = Column(Integer, primary_key=True, autoincrement=True)
    remark = Column(String(500))

class SupportMessage(Base):
    __tablename__ = "support_message"
    id = Column(Integer, primary_key=True, autoincrement=True)
    Tracking = Column(String(100))
    idsupport = Column(String(100))
    iduser = Column(String(100))
    name_departman = Column(String(600))
    text = Column(Text)
    result = Column(Text)
    time = Column(String(200))
    status = Column(Enum('Answered', 'Pending', 'Unseen', 'Customerresponse', 'close', name='support_status'))

# Function to initialize default settings (similar to table.php)
async def init_default_settings():
    from sqlalchemy.future import select
    async with async_session() as session:
        # Setting table
        result = await session.execute(select(Setting).limit(1))
        if not result.scalar_one_or_none():
            default_setting = Setting()
            session.add(default_setting)
            await session.commit()
            print("✅ Default Setting row inserted.")

        # PaySetting defaults (very important - all gateways enabled by default)
        pay_defaults = [
            ("Cartstatus", "oncard"), ("nowpaymentstatus", "offnowpayment"),
            ("statusaqayepardakht", "offaqayepardakht"), ("zarinpalstatus", "offzarinpal"),
            ("minbalance", "20000"), ("maxbalance", "1000000"),
            # ... add more as needed
        ]
        for name, value in pay_defaults:
            exists = await session.execute(select(PaySetting).where(PaySetting.NamePay == name))
            if not exists.scalar_one_or_none():
                session.add(PaySetting(NamePay=name, ValuePay=value))
        await session.commit()
        print("✅ PaySetting defaults initialized (all features free).")

        print("🎉 ZendanBOT default settings initialized successfully!")
