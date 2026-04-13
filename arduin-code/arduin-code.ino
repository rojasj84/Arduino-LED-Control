int light0_value = 0, light1_value = 0, light2_value = 0, light3_value = 0;
int remoteflag = 1; 

void setup() {
  Serial.begin(115200);
  
  // CRITICAL: Shortens the wait time for Serial functions
  Serial.setTimeout(10); 

  pinMode(5, OUTPUT);
  pinMode(6, OUTPUT);
  pinMode(9, OUTPUT);
  pinMode(10, OUTPUT);
  pinMode(12, INPUT);
}

void loop() {
  // Local Mode
  if(digitalRead(12) == HIGH){
    int light3_analog_value = analogRead(A7) / 4;
    
    // Slight deadzone handling
    if (light3_analog_value > 5) {
      analogWrite(6, light3_analog_value);
    } else {
      analogWrite(6, 0);
    }
    
    remoteflag = 1; 
    
    if (Serial.available() > 0){
      // Consume buffer quickly so it doesn't hang
      String dump = Serial.readString(); 
      Serial.print("Received: ");
      Serial.print(dump);
      Serial.println(" - Device in local mode.");
    }
  } 
  // Remote Mode
  else {
    if(remoteflag == 1){
      Serial.println("Device is in remote mode.");
      remoteflag = 0;
    }

    if(Serial.available() >= 12){ // Only read if the full 12-character packet is there
      light0_value = Serial.parseInt();
      light1_value = Serial.parseInt();
      light2_value = Serial.parseInt();
      light3_value = Serial.parseInt();
      
      analogWrite(5, light0_value);
      analogWrite(6, light1_value);
      analogWrite(9, light2_value);
      analogWrite(10, light3_value);
    }
  }
}