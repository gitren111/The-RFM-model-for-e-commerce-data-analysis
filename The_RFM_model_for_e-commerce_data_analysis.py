import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
import warnings
import missingno as msno
import plotly as py
import plotly.graph_objs as go
from plotly.io import templates
import plotly.io as pio



"""
一、项目背景
kaggle电商数据集，在英国注册的非商店在线零售的所有交易。因此本次数据分析将对客户进行分析，并对客户进行相关分层处理。
"""
#一、数据读取和概况预览
warnings.filterwarnings('ignore')
data = pd.read_csv('online_retail.csv',encoding='utf-8',dtype={'CustomerID':str})
pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', None)
pd.set_option('display.width', 1000)
print(data.head())
print(data.describe(include='all'))
#count是非空值数量，这里可以看出Description、CustomerID都有缺失

#二、数据清洗：缺失值处理、每个客户的每个订单的购买商品数量统计
data.Description = data.Description.fillna(0)
data.CustomerID = data.CustomerID.fillna('U')
print(data.describe(include='all'))
temp = data.groupby(by=['CustomerID','InvoiceNo'],as_index=False)['Quantity'].count()
#每位客户在每个发票编号下购买商品记录的数量,按照 CustomerID 和 InvoiceNo 进行分组,统计每个组中 Quantity 列的非空值数量
#temp.rename(columns={'Quantity': 'product numbers'})
print('temp\n',temp.head())

#三、退货情况分析：
#1、将退货订单与原订单匹配并创建一个列记录退货量，构建两个表分别是可以匹配、不可以匹配原订单的索引
data_cleaned = data.copy(deep=True)
data_cleaned['quantity_canceled'] = 0
unpaired_invoice = []#存储无法找到配对的取消订单索引
paired_invoice = []#存储已成功配对的取消订单索引。
for index,col in data.iterrows():
    if index % 5000 == 0:
        print(index)
    # 如果数量是正数或者是折扣商品就不处理，继续下一个迭代
    if col['Quantity'] > 0 or col['Description'] == 'Discount':
        continue
    #提取出和取消订单的商品配对的原订单
    df_test = data[(data['CustomerID'] == col['CustomerID'])
                    &(data['StockCode'] == col['StockCode'])
                    &(data['InvoiceNo'] < col['InvoiceNo'])
                    &(data['Quantity']>0)]

    if len(df_test) == 0:
        unpaired_invoice.append(index)
    # 如果匹配到一条订单，就将quantity_canceled列对应行改为退货的数量（正数），将匹配到的索引存到paired_invoice
    elif len(df_test) == 1:
        index_order = df_test.index[0]
        data_cleaned.loc[index_order,'quantity_canceled'] = -col['Quantity']
        paired_invoice.append(index)
    #优先匹配最近时间订单，当原订单数量大于等于退货订单时保存为退货订单数量
    elif len(df_test) > 1:
        df_test.sort_index(axis=0,ascending=False,inplace=True)
        for ind,val in df_test.iterrows():
            if val['Quantity'] < -col['Quantity']:
                continue#如果原订单数量比取消订单小直接跳过
            data_cleaned.loc[ind,'quantity_canceled'] = -col['Quantity']
            paired_invoice.append(index)
            break
print(data_cleaned.head())
print(len(unpaired_invoice))
print(len(paired_invoice))

#2、计算每年每月退货金额和比例，并且画图展示
data_canceled = data[data['Quantity'] <= 0]
data_all = data[data['Quantity'] > 0]
#分别加入月和年列
data_canceled['month'] = pd.to_datetime(data_canceled['InvoiceDate']).dt.month
data_all['month'] = pd.to_datetime(data_all['InvoiceDate']).dt.month
data_canceled['year'] = pd.to_datetime(data_canceled['InvoiceDate']).dt.year
data_all['year'] = pd.to_datetime(data_all['InvoiceDate']).dt.year
#计算每条订单的总价格，退货总价为负数
data_canceled['price'] = -data_canceled['Quantity'] * data_canceled['UnitPrice']
data_all['price'] = data_all['Quantity'] * data_all['UnitPrice']
#算商品总价值和退货总价值
tt = data_canceled.groupby(['year','month'])['price'].sum().unstack()
#计算每年每月的退货总价格
pp = data_all.groupby(['year','month'])['price'].sum().unstack()
print(tt)
print(pp)

# Matplotlib 中文字体设置
plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False

plt.figure(figsize=(8,6))
plt.title('各月份退货金额',fontsize=16)
plt.bar(tt.loc[2011].index,tt.loc[2011].values)

plt.figure(figsize=(8,6))
plt.title('各月份退货比例',fontsize=16)
plt.plot((tt/pp).loc[2011].index,(tt/pp).loc[2011].values)
plt.show()


"""
二、客户RFM分析：R代表客户最近一次购物消费的时间，F代表客户消费的频率, M代表客户消费总金额。
"""
#1、计算客户订单金额（包含了客户的退货情况）,汇总客户的发票金额
data_cleaned['TotalPrice'] = (data_cleaned['Quantity'] - data_cleaned['quantity_canceled']) * data_cleaned['UnitPrice']
data_cleaned.sort_values('TotalPrice')
print(data_cleaned.sort_values('TotalPrice')[:5])
#按客户和发票分组,计算每张发票的总金额,取每张发票的第一条记录的日期
invoice_price = data_cleaned.groupby(by = ['CustomerID','InvoiceNo'],as_index=False).agg({
    'TotalPrice':'sum',
    'InvoiceDate':'first'})
invoice_price.rename(columns={'TotalPrice':'basket_price'},inplace=True)
invoice_price = invoice_price.loc[invoice_price['basket_price']>0]
print(invoice_price.head(10))
#2、分别计算RMF值并画图
#确保InvoiceDate是datatime类型
invoice_price['InvoiceDate'] = pd.to_datetime(invoice_price['InvoiceDate'])
invoice_price['year'] = np.array([i.year for i in invoice_price['InvoiceDate']])
invoice_price['month'] = np.array([i.month for i in invoice_price['InvoiceDate']])
invoice_price['day'] = np.array(i.day for i in invoice_price['InvoiceDate'])

#R_value：最近一次消费时间距今天数，数据库最近开票与客户最近购物的时间差
R_value = invoice_price['InvoiceDate'].max() - invoice_price.groupby('CustomerID')['InvoiceDate'].max()
invoice_price_positive = invoice_price[invoice_price['basket_price']>0]#过滤掉退货的数据
F_value = invoice_price_positive.groupby('CustomerID')['InvoiceNo'].nunique()#计算订单/发票唯一值
M_value = invoice_price.groupby('CustomerID')['basket_price'].sum()
print(R_value.describe())
print(F_value.describe())
print(M_value.describe())
#画三个直方图
plt.figure(figsize=(8,6))
plt.title('R_value分布直方图')
plt.hist(R_value.dt.days,bins=20, color='blue', edgecolor='white')#.dt.days 将为每个时间差提取天数,bins=20: 这个参数指定了直方图的箱子数量
plt.xlabel('购物间隔天数')
plt.ylabel('顾客数量')

plt.figure(figsize=(8,6))
plt.title('F_value分布直方图')
plt.hist(F_value[F_value<20],bins=20,color='blue',edgecolor='white')
plt.xlabel('累计购物次数')
plt.ylabel('顾客数量')

plt.figure(figsize=(8,6))
plt.title('M_value分布直方图')
plt.hist(M_value[M_value<4000],bins=50,color='blue',edgecolor='white')
plt.xlabel('累计购买金额')
plt.ylabel('顾客数量')
plt.show()

#3、分箱
R_bins = [0,17,50,100,150,720]
F_bins = [1,2,3,5,20,2000]
M_bins = [0,310,700,1700,100000,2000000]
#购买天数距今越短，R_score评分越高
R_score = pd.cut(R_value.dt.days,R_bins,labels=[5,4,3,2,1],right=False).astype(int)
F_score = pd.cut(F_value,F_bins,labels=[1,2,3,4,5],right=False)
M_score = pd.cut(M_value,M_bins,labels=[1,2,3,4,5],right=False)
rmf = pd.concat([R_score,F_score,M_score],axis=1)
rmf.rename(columns={'InvoiceDate':'R_score','InvoiceNo':'F_score','basket_price':'M_score'},inplace=True)
#加入RMF列标注客户高低
rmf['R'] = np.where(rmf['R_score']>=3,'高','低')
rmf['F'] = np.where(rmf['F_score']>=3,'高','低')
rmf['M'] = np.where(rmf['M_score']>=3,'高','低')
rmf['value'] = rmf['R'] + rmf['F'] + rmf['M']
print(rmf.head(10))

#4、客户分类
    def trans_value(x):
        if x == '高高高' or x == '高低高':
            return '重要价值客户'
        elif x == '低高高' or x == '低低高' or x == '高高低':
            return '潜力客户'
        elif x == '高低低' or x == '低高低':
            return '低价值客户'
        else:
            return '流失客户'
    rmf['用户等级'] = rmf['value'].apply(trans_value)
    print(rmf['用户等级'].value_counts())

#5、客户分类画图展示:
py.offline.init_notebook_mode(connected=True)
trace_basis = [go.Bar(x = rmf['用户等级'].value_counts().index,
                      y = rmf['用户等级'].value_counts().values,
                      marker = dict(color='orange'),opacity=0.5)]
layout = {
    'title' : {'text':'客户等级概览'},
    'xaxis' : {'title':{'text':'客户等级'}}}
figure_basis = go.Figure(data = trace_basis,layout=layout)
with open('bar.html', 'w', encoding='utf-8') as f:
    f.write(figure_basis.to_html(full_html=True, include_plotlyjs='cdn'))
print('图表已保存为 bar.html，用浏览器查看')

trace = [go.Pie(labels=rmf['用户等级'].value_counts().index,
                values=rmf['用户等级'].value_counts().values,
                textfont=dict(size=12,color='white'),opacity=0.5)]
layout2 = {'title' : '用户等级比例'}
figure = go.Figure(data=trace,layout=layout2)
with open('pie.html', 'w', encoding='utf-8') as f:
    f.write(figure.to_html(full_html=True, include_plotlyjs='cdn'))
print('图表已保存为pie.html，用浏览器查看')
