import datetime
import time
import logging
from logging.handlers import RotatingFileHandler
import requests
from bs4 import BeautifulSoup
from lxml import etree

# ---------------------- 配置项 ---------------------- #
CONFIG = {
    "URL": "https://www.playthroneandliberty.com/en-us/support/server-status",
    "XPATH": '//span[contains(@class, "server-item-label") and contains(@aria-label, "Sunstorm")]',
    # --- 新增：企业微信机器人配置 ---
    "WECHAT_WEBHOOK_URL": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=",

    # <--- 【重要】替换成你的Webhook地址
    # --------------------------------
    "CHECK_INTERVAL": 6,  # 检查间隔（秒）
    "TIMEOUT": 10,  # 请求超时时间（秒）
    "LOG_FILE": "server_monitor.log",
    "USER_AGENT": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}


# ---------------------------------------------------- #

def setup_logger():
    """配置日志记录"""
    logger = logging.getLogger('ServerMonitor')
    logger.setLevel(logging.INFO)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    file_handler = RotatingFileHandler(
        CONFIG['LOG_FILE'],
        maxBytes=10 * 1024 * 1024,
        backupCount=3,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.INFO)

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger


logger = setup_logger()


# --- 新增：发送企业微信通知的函数 ---
def send_wechat_alert(content):
    """通过企业微信机器人发送文本通知"""
    if not CONFIG["WECHAT_WEBHOOK_URL"]:
        logger.error("企业微信Webhook URL未配置，无法发送通知。")
        return False

    headers = {
        'Content-Type': 'application/json'
    }

    # 构建消息体，支持@所有人
    data = {
        "msgtype": "text",
        "text": {
            "content": content,
            "mentioned_list": ["@all"]  # @所有人，如果不想@所有人，可以删除或修改此项
        }
    }

    try:
        response = requests.post(
            CONFIG["WECHAT_WEBHOOK_URL"],
            headers=headers,
            json=data,  # 使用json=data会自动序列化并设置Content-Type
            timeout=10
        )

        result = response.json()
        if result.get("errcode") == 0:
            logger.info("企业微信通知发送成功！")
            return True
        else:
            logger.error(f"企业微信通知发送失败: {result.get('errmsg', '未知错误')}")
            return False

    except requests.exceptions.RequestException as e:
        logger.error(f"发送企业微信通知时发生网络错误: {e}")
        return False
    except Exception as e:
        logger.error(f"发送企业微信通知时发生未知错误: {e}")
        return False


def get_server_status():
    """获取服务器当前状态"""
    try:
        headers = {
            'User-Agent': CONFIG['USER_AGENT'],
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        }

        response = requests.get(CONFIG['URL'], headers=headers, timeout=CONFIG['TIMEOUT'])
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "lxml")
        root = etree.HTML(str(soup))

        elements = root.xpath(CONFIG['XPATH'])
        if not elements:
            logger.warning("未找到目标元素，可能 XPath 有误或页面结构变化")
            return None

        current_status = elements[0].attrib.get("aria-label", "状态未知")
        return current_status.strip()

    except requests.exceptions.RequestException as e:
        logger.error(f"获取服务器状态失败: {e}")
        return None


def monitor_server_status():
    """监控服务器状态变化"""
    logger.info("开始监控服务器状态...")
    last_status = None

    while True:
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        current_status = get_server_status()

        if current_status:
            logger.info(f"当前状态：{current_status} | 检查时间：{current_time}")

            # 检测状态变更
            if last_status is not None and last_status != current_status:
                logger.info(f"状态变更：{last_status} → {current_status}")

                # --- 修改：调用企业微信通知函数 ---
                alert_message = (
                    f"【服务器状态变更提醒】\n"
                    f"监控时间：{current_time}\n"
                    f"服务器：Sunstorm\n"
                    f"状态变更：{last_status} → {current_status}"
                )
                send_wechat_alert(alert_message)
                return 0
            last_status = current_status

        time.sleep(CONFIG['CHECK_INTERVAL'])


def main():
    """主函数"""
    try:
        # --- 新增：测试企业微信配置 ---
        test_wechat = input("是否测试企业微信通知？(y/n): ").lower()
        if test_wechat == 'y':
            logger.info("正在测试企业微信通知...")
            send_wechat_alert("这是一条测试消息，用于验证服务器监控程序的企业微信通知功能是否正常。")

        monitor_server_status()

    except KeyboardInterrupt:
        logger.info("监控程序被手动停止")
    except Exception as e:
        logger.error(f"程序异常: {e}")


if __name__ == "__main__":
    main()
