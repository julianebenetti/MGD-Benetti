#!/usr/bin/env bash
# Liga o adb do tablet nele mesmo, para a automacao poder tocar na tela.
# Precisa de Android 11 ou mais novo.
#
#   bash conectar-adb.sh
#
set -u

echo "=============================================="
echo " Ligar o adb do tablet nele mesmo"
echo "=============================================="
echo
echo "Antes de continuar, deixe isto pronto no tablet:"
echo
echo "  1. Ajustes → Sobre o tablet → toque 7 vezes em 'Numero da versao'"
echo "  2. Ajustes → Sistema → Opcoes do desenvolvedor"
echo "  3. Ligue a 'Depuracao sem fio' (wireless debugging)"
echo "  4. Dentro dela, toque em 'Parear dispositivo com codigo'"
echo
echo "Vai aparecer uma janelinha com um codigo de 6 digitos e um endereco"
echo "tipo 192.168.0.5:41234. Deixe essa janela ABERTA."
echo
read -r -p "Endereco do PAREAMENTO (ip:porta da janelinha): " PAREAR
read -r -p "Codigo de 6 digitos: " CODIGO
echo

if ! adb pair "$PAREAR" "$CODIGO"; then
  echo
  echo "❌ o pareamento falhou."
  echo "   O endereco e o codigo mudam toda vez que a janela abre."
  echo "   Feche a janelinha, abra de novo e rode este script outra vez."
  exit 1
fi

echo
echo "✅ pareado. Agora feche a janelinha do codigo."
echo "   Na tela da 'Depuracao sem fio' aparece OUTRO endereco, logo abaixo"
echo "   de 'Endereco IP e porta'. E esse que eu preciso agora."
echo
read -r -p "Endereco da CONEXAO (ip:porta da tela principal): " CONECTAR
echo

if adb connect "$CONECTAR"; then
  echo
  adb devices
  echo
  echo "✅ pronto. Se o aparelho aparecer como 'device' na lista acima,"
  echo "   a automacao ja consegue tocar na tela."
  echo
  echo "   Guarde este endereco, ele vale ate voce desligar a depuracao:"
  echo "     $CONECTAR"
  echo
  echo "   Antes de rodar a automacao, ligue o wake lock do Termux para ele"
  echo "   nao dormir quando o app da Shopee ficar na frente:"
  echo "     termux-wake-lock"
else
  echo "❌ a conexao falhou. Confira se a depuracao sem fio continua ligada."
  exit 1
fi
