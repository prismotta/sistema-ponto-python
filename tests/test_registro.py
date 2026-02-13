from src.registro import calcular_horas

def test_calculo_horas_basico():
    entrada = "09:00:00"
    saida = "10:30:00"
    resultado = calcular_horas(entrada, saida)
    
    assert str(resultado) == "1:30:00"

def test_calculo_horas_zero():
    entrada = "09:00:00"
    saida = "09:00:00"
    resultado = calcular_horas(entrada, saida)
    
    assert str(resultado) == "0:00:00"
