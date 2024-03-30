import pdfquery
import requests
import os
from dotenv import load_dotenv
import pandas as pd
import re


load_dotenv()
EXTRAS_IN_INVOICE = ['Subtotal', 'Tax', 'Driver tip', 'Total', 'Payment method', 'TRIPLE10 promo code']


def get_initial_X(x_init, all_tags):
    '''
    Returns item labels: Checks all_tags variable and filters out the x0's that match with x_init: 
    Meant to get the y0 values for every row that starts from x_init:
    '''
    item_labels = []
    for tag in all_tags:
        if(all_tags(tag).attr('x0') == x_init):
            item_labels.append((all_tags(tag).attr('y0'), all_tags(tag).attr('y1')))
    return item_labels

def extract_remaining_columns(item_labels, all_tags):
    '''
    Returns 2-D array/list, with all data extracted from the PDF:
    Based on the y0's from get_initial_X method, checks every element in the PDF to obtain all text objects that start from same height as the item label/first column:
    '''
    extracted_data = []
    for y0, y1 in item_labels:
        row_data = {}
        for tag in all_tags:
            if((all_tags(tag).attr('y0') == y0) or (all_tags(tag).attr('y0')>=y0 and all_tags(tag).attr('y0')<=y1)):
                cell_value = all_tags(tag).text()
                if(re.findall("(Shopped|Unavailable|Weight-adjusted|Ending in)(\s)?(Qty)?", cell_value)):
                    row_data['itemQuantity'] = cell_value
                    start_index = re.search("(Shopped|Unavailable|Weight-adjusted|Ending in)(\s)?(Qty)?", cell_value).start()
                    if(start_index != 0):
                        row_data['itemName'] = cell_value[0:start_index]
                        row_data['itemQuantity'] = cell_value[start_index:]
                elif(re.findall("\$\s?[0-9]*\.[0-9]*", cell_value)):
                    row_data['itemPrice'] = cell_value
                else:
                    if(re.findall("Qty\s?[0-9]*", cell_value)):
                        row_data['itemQuantity'] = cell_value
                    else:
                        row_data['itemName'] = cell_value
        extracted_data.append(row_data)
    return extracted_data

def prepare_data_to_create_order(data):
    '''
    formats data to send POST request to API to create the order
    key-value of the result_data attribute are formatted according to the requirements of ModelSchema in API
    '''
    tp_order_details = data[0].get('itemName').split('\n')
    order_items = []
    invoice_extras = {}
    # print(data)
    for index in range(1, len(data)):
        if(data[index].get('itemName') in EXTRAS_IN_INVOICE): #FIND A WAY TO OPTIMIZE THIS, CURRENTLY WE NEED TO HAVE EXACT TAG FROM THE INVOICE IN EXTRAS_IN_INVOICE VARIABLE BUT IT CAN KEEP GROWING TRY MAKING THIS GENERIC
            if(data[index].get('itemPrice') is None):
                invoice_extras[data[index].get('itemName')] = data[index].get('itemQuantity')
            else:
                invoice_extras[data[index].get('itemName')] = float(str(data[index].get('itemPrice')).replace('$', ''))
        else:
            print(data[index])
            data[index]['itemPrice'] = float(data[index].get('itemPrice', '$0').replace('$', ''))
            order_items.append(data[index])
    result_dict = {'orderDate': tp_order_details[0], 'invoiceOrderId': tp_order_details[1], 'itemsList': order_items}
    result_dict.update(invoice_extras)
    return result_dict

'''TRY ADDING ASYNC TO IMPROVE EFFICIENCY'''
def post_order(order_dict):
    '''
    Sends the POST request to the API 
    * May need to add CORS headers to the request object
    '''
    try:
        server = os.getenv('SERVER')
        port = os.getenv('PORT')
        urlpath = os.getenv('ORDER_POST_URLPATH')
        url = f'http://{server}:{port}/{urlpath}'
        # print(order_dict)
        response = requests.post(url=url, json=order_dict)
        print(response.json())
    except Exception as ex:
        print(ex) 


if __name__ == '__main__':
    pdf = pdfquery.PDFQuery(file='Order details - Walmart.com - 5.pdf')
    page_count = pdf.doc.catalog['Pages'].resolve()['Count']
    x_init = 0
    extracted_data = []
    for page_index in range(page_count):
        pdf.load(page_index)
        pdf.tree.write(f'Order details - Walmart.com-{page_index}.xml', pretty_print=True) #Not needed, generates xml file --debugging purpose only
        if(page_index == 0):
            order_tag = pdf.pq('LTTextBoxHorizontal:contains("Order#")') #PDFQuery object using "Order#"" for initial x0
            x_init = order_tag.attr('x0') #Initial value for x0
        all_tags = pdf.pq('LTTextBoxHorizontal') #All tags inside LTTextBoxHorizontal element
        item_labels = get_initial_X(x_init=x_init, all_tags=all_tags)
        extracted_data.extend(extract_remaining_columns(item_labels=item_labels, all_tags=all_tags))
    print(pd.DataFrame(extracted_data))
    data_to_be_POSTed = prepare_data_to_create_order(extracted_data)
    
    '''ADJUSTING GROUP ID FOR TESTING'''
    data_to_be_POSTed.update({'groupId': '65ef977856ddf380905b80e5'})
    
    post_order(data_to_be_POSTed)