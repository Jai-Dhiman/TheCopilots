cat > /tmp/merge.py << 'EOF'
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel
print('Loading base model in bf16...')
model = AutoModelForCausalLM.from_pretrained('google/gemma-3-1b-it', torch_dtype=torch.bfloat16, device_map='auto')
tokenizer = AutoTokenizer.from_pretrained('google/gemma-3-1b-it')
print('Loading LoRA adapter...')
model = PeftModel.from_pretrained(model, 'models/gemma3-gdt-lora')
print('Merging...')
model = model.merge_and_unload()
print('Saving...')
model.save_pretrained('models/gemma3-gdt-merged')
tokenizer.save_pretrained('models/gemma3-gdt-merged')
print('Done.')
EOF
python3 /tmp/merge.py
