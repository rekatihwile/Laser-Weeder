from Laser_Helpers import send, connect, close, move_to, burn

ser = connect()
send(ser, "$H") 

move_to(ser, 400, 55)
burn(ser,300,0.45)

move_to(ser, 400, 110)
burn(ser,300,0.45)

move_to(ser, 350, 110)
burn(ser,300,0.45)

move_to(ser, 350, 165)
burn(ser,300,0.45)

move_to(ser, 300, 165)
burn(ser,300,0.45)

