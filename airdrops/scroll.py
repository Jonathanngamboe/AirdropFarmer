# scroll

airdrop_info = {
    "name": "Scroll",
    "isActivated": True,
    "actions": [
            {
            "platform": "defi",
            "isActivated": True,
            "blockchain": "goerli",
            "action": "interact_with_contract",
            "contract_address": '0xe5E30E7c24e4dFcb281A682562E53154C15D3332',
            "abi": [{"anonymous":False,"inputs":[{"indexed":True,"internalType":"address","name":"l1Token","type":"address"},{"indexed":True,"internalType":"address","name":"l2Token","type":"address"},{"indexed":True,"internalType":"address","name":"from","type":"address"},{"indexed":False,"internalType":"address","name":"to","type":"address"},{"indexed":False,"internalType":"uint256","name":"amount","type":"uint256"},{"indexed":False,"internalType":"bytes","name":"resources","type":"bytes"}],"name":"DepositERC20","type":"event"},{"anonymous":False,"inputs":[{"indexed":True,"internalType":"address","name":"from","type":"address"},{"indexed":True,"internalType":"address","name":"to","type":"address"},{"indexed":False,"internalType":"uint256","name":"amount","type":"uint256"},{"indexed":False,"internalType":"bytes","name":"resources","type":"bytes"}],"name":"DepositETH","type":"event"},{"anonymous":False,"inputs":[{"indexed":True,"internalType":"address","name":"l1Token","type":"address"},{"indexed":True,"internalType":"address","name":"l2Token","type":"address"},{"indexed":True,"internalType":"address","name":"from","type":"address"},{"indexed":False,"internalType":"address","name":"to","type":"address"},{"indexed":False,"internalType":"uint256","name":"amount","type":"uint256"},{"indexed":False,"internalType":"bytes","name":"resources","type":"bytes"}],"name":"FinalizeWithdrawERC20","type":"event"},{"anonymous":False,"inputs":[{"indexed":True,"internalType":"address","name":"from","type":"address"},{"indexed":True,"internalType":"address","name":"to","type":"address"},{"indexed":False,"internalType":"uint256","name":"amount","type":"uint256"},{"indexed":False,"internalType":"bytes","name":"resources","type":"bytes"}],"name":"FinalizeWithdrawETH","type":"event"},{"anonymous":False,"inputs":[{"indexed":True,"internalType":"address","name":"previousOwner","type":"address"},{"indexed":True,"internalType":"address","name":"newOwner","type":"address"}],"name":"OwnershipTransferred","type":"event"},{"anonymous":False,"inputs":[{"indexed":True,"internalType":"address","name":"defaultERC20Gateway","type":"address"}],"name":"SetDefaultERC20Gateway","type":"event"},{"anonymous":False,"inputs":[{"indexed":True,"internalType":"address","name":"token","type":"address"},{"indexed":True,"internalType":"address","name":"gateway","type":"address"}],"name":"SetERC20Gateway","type":"event"},{"anonymous":False,"inputs":[{"indexed":True,"internalType":"address","name":"ethGateway","type":"address"}],"name":"SetETHGateway","type":"event"},{"inputs":[{"internalType":"address","name":"","type":"address"}],"name":"ERC20Gateway","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"defaultERC20Gateway","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"_token","type":"address"},{"internalType":"uint256","name":"_amount","type":"uint256"},{"internalType":"uint256","name":"_gasLimit","type":"uint256"}],"name":"depositERC20","outputs":[],"stateMutability":"payable","type":"function"},{"inputs":[{"internalType":"address","name":"_token","type":"address"},{"internalType":"address","name":"_to","type":"address"},{"internalType":"uint256","name":"_amount","type":"uint256"},{"internalType":"uint256","name":"_gasLimit","type":"uint256"}],"name":"depositERC20","outputs":[],"stateMutability":"payable","type":"function"},{"inputs":[{"internalType":"address","name":"_token","type":"address"},{"internalType":"address","name":"_to","type":"address"},{"internalType":"uint256","name":"_amount","type":"uint256"},{"internalType":"bytes","name":"_data","type":"bytes"},{"internalType":"uint256","name":"_gasLimit","type":"uint256"}],"name":"depositERC20AndCall","outputs":[],"stateMutability":"payable","type":"function"},{"inputs":[{"internalType":"uint256","name":"_amount","type":"uint256"},{"internalType":"uint256","name":"_gasLimit","type":"uint256"}],"name":"depositETH","outputs":[],"stateMutability":"payable","type":"function"},{"inputs":[{"internalType":"address","name":"_to","type":"address"},{"internalType":"uint256","name":"_amount","type":"uint256"},{"internalType":"uint256","name":"_gasLimit","type":"uint256"}],"name":"depositETH","outputs":[],"stateMutability":"payable","type":"function"},{"inputs":[{"internalType":"address","name":"_to","type":"address"},{"internalType":"uint256","name":"_amount","type":"uint256"},{"internalType":"bytes","name":"_data","type":"bytes"},{"internalType":"uint256","name":"_gasLimit","type":"uint256"}],"name":"depositETHAndCall","outputs":[],"stateMutability":"payable","type":"function"},{"inputs":[],"name":"ethGateway","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"","type":"address"},{"internalType":"address","name":"","type":"address"},{"internalType":"address","name":"","type":"address"},{"internalType":"address","name":"","type":"address"},{"internalType":"uint256","name":"","type":"uint256"},{"internalType":"bytes","name":"","type":"bytes"}],"name":"finalizeWithdrawERC20","outputs":[],"stateMutability":"payable","type":"function"},{"inputs":[{"internalType":"address","name":"","type":"address"},{"internalType":"address","name":"","type":"address"},{"internalType":"uint256","name":"","type":"uint256"},{"internalType":"bytes","name":"","type":"bytes"}],"name":"finalizeWithdrawETH","outputs":[],"stateMutability":"payable","type":"function"},{"inputs":[{"internalType":"address","name":"_token","type":"address"}],"name":"getERC20Gateway","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"_l1Address","type":"address"}],"name":"getL2ERC20Address","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"_ethGateway","type":"address"},{"internalType":"address","name":"_defaultERC20Gateway","type":"address"}],"name":"initialize","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[],"name":"owner","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"renounceOwnership","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address","name":"_defaultERC20Gateway","type":"address"}],"name":"setDefaultERC20Gateway","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address[]","name":"_tokens","type":"address[]"},{"internalType":"address[]","name":"_gateways","type":"address[]"}],"name":"setERC20Gateway","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address","name":"_ethGateway","type":"address"}],"name":"setETHGateway","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address","name":"newOwner","type":"address"}],"name":"transferOwnership","outputs":[],"stateMutability":"nonpayable","type":"function"}],
            "function_name": "depositETH",
            "msg_value": 10000040000000000,
            "function_args": {
                "_amount": 10000040000000000,
                "_gasLimit": 40000,
            }
        }
    ]
}
