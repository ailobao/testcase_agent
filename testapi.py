from testcase_agent import generate_api_test_cases

cases = generate_api_test_cases(
    project_name='客达天下',
    module_name='新增课程',
    test_type='',
    num=5,
    business_rules='POST /api/clues/course 参数：name,subject,price,applicablePerson 生成5条用例'
)

print(f'生成数量: {len(cases)}')
if cases:
    print(f'第一条标题: {cases[0].get("title")}')
else:
    print('没有生成任何用例')