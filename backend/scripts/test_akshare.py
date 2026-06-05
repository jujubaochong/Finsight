"""
测试 AkShare 数据获取问题
"""
import sys
sys.path.append('.')
import time
import akshare as ak

def test_akshare_apis():
    """测试所有可能用到的 AkShare 接口"""
    print("=== 测试 AkShare 接口 ===")
    
    apis_to_test = [
        ("stock_info_a_code_name", "A股股票列表"),
        ("stock_financial_analysis_indicator", "财务分析指标"),
        ("stock_financial_report_sina", "新浪财务报告"),
        ("stock_notice_report", "公告报告"),
    ]
    
    for func_name, description in apis_to_test:
        try:
            print(f"\n测试: {description} ({func_name})")
            time.sleep(0.6)  # 避免限频
            
            if func_name == "stock_info_a_code_name":
                df = ak.stock_info_a_code_name()
            elif func_name == "stock_financial_analysis_indicator":
                df = ak.stock_financial_analysis_indicator(symbol="000001")
            elif func_name == "stock_financial_report_sina":
                df = ak.stock_financial_report_sina(stock="000001", symbol="利润表")
            elif func_name == "stock_notice_report":
                df = ak.stock_notice_report(symbol="000001")
            else:
                df = None
                
            if df is None:
                print(f"  ❌ 返回 None")
            elif df.empty:
                print(f"  ⚠️  数据为空 (形状: {df.shape})")
            else:
                print(f"  ✅ 成功 (形状: {df.shape})")
                print(f"     列名: {list(df.columns)[:10]}...")  # 只显示前10列
                if len(df) > 0:
                    print(f"     首行示例: {dict(df.iloc[0].head())}")
                    
        except Exception as e:
            print(f"  ❌ 异常: {e}")

def test_simple_financial():
    """测试一个简单的财务数据获取方式"""
    print("\n=== 测试简单财务数据获取 ===")
    
    # 测试一些简单的股票数据接口
    test_codes = ["000001", "600519", "000002"]
    
    for code in test_codes:
        try:
            print(f"\n测试股票 {code}:")
            
            # 1. 测试股票基本信息
            time.sleep(0.6)
            try:
                df_info = ak.stock_individual_info_em(symbol=code)
                if df_info is not None and not df_info.empty:
                    print(f"  基本信息: ✅ ({len(df_info)} 条)")
                    # 显示一些关键信息
                    for _, row in df_info.iterrows():
                        if row['item'] in ['股票简称', '所属行业', '上市日期']:
                            print(f"    {row['item']}: {row['value']}")
                else:
                    print(f"  基本信息: ⚠️ 空数据")
            except Exception as e:
                print(f"  基本信息: ❌ {e}")
            
            # 2. 测试简单的财务指标
            time.sleep(0.6)
            try:
                df_simple = ak.stock_financial_abstract(symbol=code)
                if df_simple is not None and not df_simple.empty:
                    print(f"  财务摘要: ✅ ({df_simple.shape})")
                    print(f"    最新报告期: {df_simple.iloc[0]['REPORT_DATE'] if 'REPORT_DATE' in df_simple.columns else 'N/A'}")
                else:
                    print(f"  财务摘要: ⚠️ 空数据")
            except Exception as e:
                print(f"  财务摘要: ❌ {e}")
                
        except Exception as e:
            print(f"  整体失败: {e}")

if __name__ == "__main__":
    test_akshare_apis()
    test_simple_financial()