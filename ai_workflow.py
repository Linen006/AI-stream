"""AI 工作流 CLI（兼容入口）：商品 -> 卖点 -> 内容角度 -> 脚本分镜 -> 质检 -> 回写。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.services import workflow_service
from app.services.workflow_service import append_csv, load_products, next_id  # noqa: F401


def custom_product() -> dict:
    print("\n  [自定义模式]")
    name = input("  商品名称：").strip()
    if not name:
        raise SystemExit("  商品名称不能为空")
    return {
        "id": "P099",
        "name": name,
        "price": input("  价格区间：").strip() or "待定",
        "target_audience": input("  目标人群：").strip() or "待定",
        "selling_points": input("  核心卖点：").strip() or "待定",
    }


def main() -> None:
    print("=" * 60)
    print("  AI 工作流 - 商品营销内容自动生成系统")
    print("  数据来源：data/products.csv | 回写：scripts.csv + ecommerce.db")
    print("=" * 60)

    products = load_products()
    for i, p in enumerate(products):
        print(f"  [{i+1}] {p['name']}（{p['price']}）")
    print(f"  [{len(products)+1}] 自定义商品")
    print("  [q] 退出")

    while True:
        choice = input(f"\n  请选择商品（1-{len(products)+1}）：").strip().lower()
        if choice == "q":
            return
        try:
            idx = int(choice)
            if 1 <= idx <= len(products):
                product = products[idx - 1]
            elif idx == len(products) + 1:
                product = custom_product()
            else:
                print(f"  请输入1-{len(products)+1}之间的数字")
                continue
            result = workflow_service.run_workflow(product, auto_approve=False)
            print(f"\n  [完成] 脚本编号 {result['script_id']}，目录 {result['output_dir']}")
            return
        except ValueError:
            print("  请输入有效数字")


if __name__ == "__main__":
    main()
