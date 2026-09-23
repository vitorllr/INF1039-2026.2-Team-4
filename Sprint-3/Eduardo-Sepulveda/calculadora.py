def soma(a, b):
    return(a + b)

def multiplica(a, b):
    return(a * b)

def sub(a, b):
    return(a - b)

def div(a, b):
    return(a/b)

pergunta = int(input("Qual operação você quer fazer: \n 1-Soma 2-Multiplicação 3-Subtração 4-Divisão"))
num1 = float(input("Me diga o número A: "))
num2 = float(input("Me diga o número B: "))

if pergunta == 1:
    print(soma(num1, num2))
elif pergunta == 2:
    print(multiplica(num1, num2))
elif pergunta == 3:
    print(sub(num1, num2))
elif pergunta == 4:
    print(div(num1,num2))
else:
    print("Não entendi, você provavelmente escreveu algo errado")