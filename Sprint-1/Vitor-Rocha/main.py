def calcula_soma(x, y):
    return x + y


def calcula_subtracao(x, y):
    return x - y


def calcula_multiplicacao(x, y):
    return x * y


def calcula_divisao(x, y):
    return x / y


running = True
while running:
    print("Escolha uma das opcoes:\n")
    print("1-Adicao \n")
    print("2-Subtracao:\n")
    print("3-Multiplicacao:\n")
    print("4-Divisao:\n")

    escolha = int(input())
    num1 = int(input("Escolha o primeiro numero: "))
    num2 = int(input("Escolha o segundo numero: "))

    if escolha == 1:
        print(f"O Resultado e: {calcula_soma(num1, num2)}")
    elif escolha == 2:
        print(f"O Resultado e: {calcula_subtracao(num1, num2)}")
    elif escolha == 3:
        print(f"O Resultado e: {calcula_multiplicacao(num1, num2)}")
    elif escolha == 4:
        print(f"O Resultado e: {calcula_divisao(num1, num2)}")

    continuar = input("Deseja continuar (s/n)")

    if continuar.strip() != "s":
        running = False