"""脚本生成助手 CLI（兼容入口）。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.services import agent_service
from app.services.agent_service import load_prompt, validate_input, validate_output  # noqa: F401


def main() -> None:
    print("")
    print("=" * 60)
    print("  脚本生成助手 v2.0")
    print("  输入商品名称，AI自动分析并生成短视频脚本")
    print("  知识库提示词：knowledge/prompts.json")
    print("=" * 60)

    while True:
        print("\n" + "-" * 60)
        print("  [新任务] 输入商品名称（输入 q 退出）")
        try:
            raw = input("  商品名称：").strip()
            if raw.lower() == "q":
                break
            name = validate_input(raw)
        except ValueError as e:
            print(f"  [输入错误] {e}")
            continue

        print("\n  [AI正在分析商品...]")
        try:
            suggestion = agent_service.ai_analyze_product(name)
        except Exception as e:
            print(f"  [错误] {e}")
            continue

        print(f"\n  [AI分析建议]\n{suggestion}")

        confirm = input("\n  使用以上AI建议？(y=直接使用 / n=自己填写)：").strip().lower()
        if confirm == "y":
            audience = scenario = sell = "(AI自动分析)"
        else:
            audience = input("  目标人群：").strip() or "(AI自动分析)"
            scenario = input("  使用场景：").strip() or "(AI自动分析)"
            sell = input("  核心卖点：").strip() or "(AI自动分析)"

        print("\n  [AI正在生成脚本...]")
        try:
            result = agent_service.generate_script(name, audience, scenario, sell)
            saved = agent_service.save_script_result(name, audience, scenario, sell, result)
        except Exception as e:
            print(f"  [错误] {e}")
            continue

        print("\n" + "-" * 60)
        print("  [智能体输出]\n")
        print(result)
        print(f"\n  [已保存] {saved['saved_to']}（编号 {saved['script_id']}）")

        again = input("\n  继续生成下一个？(y/n)：").strip().lower()
        if again != "y":
            break

    print("\n  感谢使用脚本生成助手！")
    try:
        input("  按 Enter 键退出...")
    except EOFError:
        pass


if __name__ == "__main__":
    main()
