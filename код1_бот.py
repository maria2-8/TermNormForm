import telebot
import os
from dotenv import load_dotenv
import nltk
from nltk.tokenize import RegexpTokenizer
import pymorphy2
nltk.download('punkt_tab')

#загружаем значение токена
def get_token(key):
    dotenv_path = os.path.join(os.path.dirname(__file__), 'for_bot.env')
    if os.path.exists(dotenv_path):
        load_dotenv(dotenv_path)
        return os.getenv(key)

#записываем токен в переменную
token = get_token('bot_token')

mybot = telebot.TeleBot(token, parse_mode=None)  #объект класса TeleBot

#сообщение, которое бот присылает в чат по команде /start
@mybot.message_handler(commands=['start'])
def send_welcome(message):
    mybot.reply_to(message, "Привет! Напиши предложение, я найду термины")

#обработка предложения, введенного пользователем
@mybot.message_handler(content_types=["text"])
def message_tokens(message):
    #делаем токенизацию предложения с помощью регулярных выражений
    #r'\w+' значит, что токены будут последовательностями, состоящими из одного или более буквенных символов
    reg_tokenizer = RegexpTokenizer(r'\w+')
    tokens = reg_tokenizer.tokenize(message.text)
    morph = pymorphy2.MorphAnalyzer() #класс для морфологического анализа слов
    pos_lst = [] #в этот список записывается часть речи для каждого токена
    ext_pos_lst = [] #"расширенный" список (здесь часть речи, падеж, число, начальная форма, род для каждого токена)
    for t in tokens:
        parse = morph.parse(t)
        POS = parse[0].tag.POS #часть речи
        pos_lst.append(POS)
        case = parse[0].tag.case #падеж
        num = parse[0].tag.number #число
        norm = parse[0].normal_form #начальная форма
        #если падеж или род не определены, добавляем пустую строку
        if case is None:
            case = ' '
        gender = parse[0].tag.gender
        if gender is None:
            gender = ' '
        ext_pos_lst.append((t, POS, case, gender, norm, num)) #токен, часть речи, падеж, род, начальная форма, число

    #определяем одиночное существительное как самостоятельный термин (на всякий случай)
    for i in range(len(ext_pos_lst)):
        if ext_pos_lst[i][1] == 'NOUN':
            mybot.send_message(message.chat.id, str(ext_pos_lst[i][4])) #отправка сообщения в чат

    #два существительных, второе в род. падеже (пример термина: "распределение вероятностей")
    for i in range(len(ext_pos_lst)-1):
        if ext_pos_lst[i][1] == 'NOUN' and ext_pos_lst[i+1][1] == 'NOUN' and ext_pos_lst[i+1][2] == 'gent':
            small_list = []
            small_list.append(ext_pos_lst[i][4]) #выдаем первое существительное в начальной форме
            small_list.append(ext_pos_lst[i+1][0]) #а второе (которое в род. падеже) - в той же форме, как во входном предложении
            res_str = ' '.join(small_list) #создаем строку "сущ. + сущ."
            mybot.send_message(message.chat.id, str(res_str)) #отправляем строку в чат

    #прил. + сущ. (пример термина: "китайская интерференция")
    for i in range(len(ext_pos_lst) - 1):
        if ext_pos_lst[i][1] == 'ADJF' and ext_pos_lst[i + 1][1] == 'NOUN':
            r_dict = {}
            #морфологические разборы прилагательного
            adj_parses = morph.parse(ext_pos_lst[i][0])
            #морфологические разборы существительного
            noun_parses = morph.parse(ext_pos_lst[i + 1][0])
            for a_parse in adj_parses:
                for n_parse in noun_parses:
                    if 'plur' in a_parse.tag.number or a_parse.tag.gender is None:
                        #для прилагательных во множ. числе определяем род по существительному, если у этих прил. и сущ. совпадает число и падеж
                        if a_parse.tag.number == n_parse.tag.number and a_parse.tag.case == n_parse.tag.case:
                            r_dict[a_parse.tag.POS] = {"номер": adj_parses.index(a_parse), "род": n_parse.tag.gender,
                                                       "число": a_parse.tag.number, "падеж": a_parse.tag.case}
                            r_dict[n_parse.tag.POS] = {"номер": noun_parses.index(n_parse), "род": n_parse.tag.gender,
                                                       "число": n_parse.tag.number, "падеж": n_parse.tag.case}
                    else:
                        #если прилагательное в единственном числе, у него должны совпадать с существительным число, род и падеж
                        if a_parse.tag.gender == n_parse.tag.gender and a_parse.tag.number == n_parse.tag.number and a_parse.tag.case == n_parse.tag.case:
                            r_dict[a_parse.tag.POS] = {"номер": adj_parses.index(a_parse), "род": a_parse.tag.gender,
                                                       "число": a_parse.tag.number, "падеж": a_parse.tag.case}
                            r_dict[n_parse.tag.POS] = {"номер": noun_parses.index(n_parse), "род": n_parse.tag.gender,
                                                       "число": n_parse.tag.number, "падеж": n_parse.tag.case}

            a_parse_num = r_dict['ADJF']['номер']
            n_parse_num = r_dict['NOUN']['номер']

            if r_dict['ADJF']['род'] is None:
                a_norm = adj_parses[a_parse_num].inflect({'sing', 'nomn'})
                n_norm = noun_parses[n_parse_num].inflect({'sing', 'nomn'})
                res = str(a_norm.word + ' ' + n_norm.word) #создаем строку "прил. + сущ."
                mybot.send_message(message.chat.id, res) #отправляем строку в чат
            else:
                a_norm = adj_parses[a_parse_num].inflect({'sing', r_dict['ADJF']['род'], 'nomn'})
                n_norm = noun_parses[n_parse_num].inflect({'sing', r_dict['NOUN']['род'], 'nomn'})
                res = str(a_norm.word + ' ' + n_norm.word) #создаем строку "прил. + сущ."
                mybot.send_message(message.chat.id, res) #отправляем строку в чат

    #шаблон термина: сущ., прил., сущ. (пример: "фонетика английского языка")
    for i in range(len(ext_pos_lst) - 2):
        if ext_pos_lst[i][1] == 'NOUN' and (ext_pos_lst[i+1][1] == 'ADJF' and ext_pos_lst[i+1][2] == 'gent') and (ext_pos_lst[i+2][1] == 'NOUN' and ext_pos_lst[i+1][2] == 'gent'):
            first_noun_norm = ext_pos_lst[i][4] #приводим первое существительное к начальной форме
            #прилагательное и второе существительное оставляем в такой форме, как во входном предложении
            str_res = first_noun_norm + ' ' + ext_pos_lst[i+1][0] + ' ' + ext_pos_lst[i+2][0]
            mybot.send_message(message.chat.id, str(str_res))

mybot.infinity_polling()
#infinity_polling() значит, что сервер будет открытым (бот будет ждать новых сообщений), пока не закрыть программу