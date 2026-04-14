import re
filepath = r"C:/Users/11526/OneDrive/Desktop/分子对接评价指南_同批次内容_20260319_150844/01_相关文档/分析文档/【分子对接分析报告】3VVP_P-glycoprotein_C952A.md"
with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()
for i, line in enumerate(lines):
    if '对接评分' in line:
        print(i, line.strip())
        # 打印后续几行
        for j in range(i, min(i+20, len(lines))):
            print(f"{j}: {lines[j].rstrip()}")
        break