package.path='/opt/tarantool/?.lua;/opt/tarantool/?/init.lua;/opt/TarantoolModules/?.lua;/opt/TarantoolModules/?/init.lua;'..package.path

local function DoPercentEncoding(s)
  local function char_to_hex(c)
    return string.format("%%%02X",string.byte(c))
  end
  return s and s:gsub("\n", "\r\n"):gsub("([^%w ])",char_to_hex):gsub(" ", "+")
end

box.cfg{
  listen=3301,
  work_dir='/var/lib/tarantool',
  wal_dir = 'WAL',
  memtx_dir = 'MemTX',
  vinyl_dir = 'Vinyl'
}

local Cfg=require("Config")

local console=require('console')
console.listen('/var/lib/tarantool/admin.sock')
local log=require('log')
local json=require('json')
local crypto=require('crypto')
local clock=require('clock')
local http_client=require('http.client').new({max_connections=5})
--local string=require('string')
local base58=require("base58")

--Spaces
local Users=box.space.Users
local UsersEx=box.space.UsersEx
local UsersOAuth=box.space.UsersOAuth
local Decks=box.space.Decks
local DeckCards=box.space.DeckCards

--functions
local function MkUser(MainRecord,SecondaryRecord)
  return {
    ID=MainRecord[1],
    Name=MainRecord[2],
    Email=MainRecord[3],
    TrueUser=MainRecord[5]=='Admin' or MainRecord[5]=='Test',
    IsAdmin=MainRecord[5]=='Admin',
    Enabled=MainRecord[6],
    Mailing=MainRecord[7],
    Session=MainRecord[8],
    --=SecondaryRecord[],
  }
end

local function VerifyAdmin(Session)
  local Res=Users.index.Session:select(Session)
  return #Res==1 and Res[1][6] and Res[1][5]=='Admin'
end
local function GenPassword()
  return
end

local Salt=tostring(clock.time64())
local function MkSession()
  return base58.encode_base58(crypto.digest.sha512(tostring(clock.time64())..Salt))
end
local function CryptoPassword(Password)
  return crypto.digest.sha512(Password..'-1022ee7c9ea5781e58d16bef46d10a3be6b8d226d14186f3810fcfc3250a68ed75c0fec80020cc55b4105d700ef8cefbe70508f8e4c1c40c90d4b599b3a90ae6')
end

box.once("schema",function()
  -- основной пользователь
  box.schema.user.passwd(Cfg.Tarantool.AdminPassword)

  -- настроить пользователя для репликации
  box.schema.user.create('replicator', {password = 'password'})
  box.schema.user.grant('replicator', 'replication')

  Users=box.schema.space.create('Users',{engine="vinyl",format={
    {name='ID',type='unsigned'},
    {name='Name',type='string'},
    {name='Email',type='string'},
    {name='Password',type='string'},
    {name='Type',type='string',is_nullable=true},  --Admin|Test|nil
    {name='Enabled',type='boolean'},
    {name='Mailing',type='boolean'},
    {name='Session',type='string',is_nullable=true},
    {name='Code',type='string',is_nullable=true}
    --unsigned|string|integer|number|boolean|array|scalar
  }})
  box.schema.sequence.create('UsersSeq')
  Users:create_index('primary',{unique=true,parts={{1,"unsigned"}},sequence='UsersSeq'})
  Users:create_index('Login',{unique=true,parts={{3,"string"},{4,"string"}}})
  Users:create_index('Email',{unique=true,parts={{3,"string"}}})
  Users:create_index('Mailing',{unique=false,parts={{7,"boolean"}}})
  Users:create_index('Session',{unique=true,parts={{8,"string"}}})
  Users:create_index('Code',{unique=true,parts={{9,"string"}}})

  UsersEx=box.schema.space.create('UsersEx',{engine="vinyl",format={
    {name='ID',type='unsigned'},
    {name='Image',type='string',is_nullable=true},
    {name='Website',type='string',is_nullable=true}
  }})
  UsersEx:create_index('primary',{unique=true,parts={{1,"unsigned"}}})

  local U=Users:insert({nil,'UberAdmin','teamfnd@yandex.ru',CryptoPassword('yz9zkq'),'Admin',true,false,'AdminTestSession',nil})
  UsersEx:insert({U[1]})

  UsersOAuth=box.schema.space.create('UsersOAuth',{engine="vinyl",format={
    {name='UserID',type='unsigned'},
    {name='OAuth',type='string'},
    {name='OAuthID',type='unsigned'}
  }})
  UsersOAuth:create_index('primary',{unique=true,parts={{2,"string"},{3,"unsigned"}}})

  Decks=box.schema.space.create('Decks',{engine="vinyl",format={
    {name='UserID',type='unsigned'},
    {name='ID',type='unsigned'},
    {name='Name',type='string'},
    {name='Class',type='unsigned'},
    {name='Type',type='unsigned'}
  }})
  box.schema.sequence.create('DecksSeq')
  Decks:create_index('primary',{unique=true,parts={{2,"unsigned"}},sequence='DecksSeq'})
  Decks:create_index('Text',{unique=true,parts={{1,"unsigned"},{3,"string"}}})
  Decks:create_index('User',{unique=false,parts={{1,"unsigned"}}})

  DeckCards=box.schema.space.create('DeckCards',{engine="vinyl",format={
    {name='DeckID',type='unsigned'},
    {name='CardSet',type='string'},
    {name='CardName',type='string'}
  }})
  DeckCards:create_index('primary',{unique=true,parts={{1,"unsigned"},{2,"string"},{3,"string"}}})
  DeckCards:create_index('ID',{unique=false,parts={{1,"unsigned"}}})
end)

function VerifyEmail(Code)
  if #Users.index.Code:select(Code)==1 then
    Users.index.Code:update(Code,{{'=',6,true},{'#',9,1}})
    return 200
  else
    return 404
  end
end

function CheckEmail(Email)
  return #Users.index.Email:select(Email)>0 and 409 or 200
end

function RegisterUser(UserName,Email,Password,Mailing)
  local Result
  if Users.index.Email:get(Email) then
    return 409
  elseif pcall(function()
      Result=Users:insert{nil,UserName,Email,CryptoPassword(Password),nil,false,Mailing,nil,MkSession()}
      UsersEx:insert{Result[1]}
    end)then
    local link=[[https://languagerobbers.ru/VerifyEmail?Code=]]..Result[9]
    local r=http_client:get([[https://languagerobbers.ru/SendMail?Key=]]..Cfg.InternalKey.."&Email="..DoPercentEncoding(Email).."&Subject="..DoPercentEncoding("Подтверждение регитсрации на Language Robbers").."&Body="..
      DoPercentEncoding("Уважемый "..UserName..
      '<p>Спасибо за регистрацию на languagerobbers.ru!<p>Для подтверждения вашего email адреса перейдите по следующей ссылке:'..
      '<p><a href="'..link..'">'..link..'</a>'))
    log.error(r.status)
    log.error(r.body)
    log.error(r.reason)
    return r.status
  else
    return 500
  end
end

function RegisterUserOAuth(key,UserName,Email,ServiceName,ServiceID)
  if key==Cfg.InternalKey then
    local Result
    if Users.index.Email:get(Email) then
      return 409
    elseif pcall(function()
        Result=Users:insert{nil,UserName,Email,'',nil,false,false,nil,MkSession()}
        UsersEx:insert{Result[1]}
        UsersOAuth:insert{Result[1],ServiceName,ServiceID}
      end)then
      return 200,Result[9]
    else
      return 500
    end
  else
    return 200
  end
end

function RegisterUserOAuthVerify(Code,Password,Mailing)
  if Users.index.Code:get(Code) then
    local Session=MkSession()
    Users.index.Code:update(Code,{{'=',4,CryptoPassword(Password)},{'=',6,true},{'=',7,Mailing},{'=',8,Session},{'#',9,1}})
    return 200,Session
  else
    return 404
  end
end

function GetCurrUser(Session)
  local Res=Users.index.Session:select(Session)
  if #Res==1 and Res[1][6] then
    return 200,MkUser(Res[1],UsersEx:get(Res[1][1]))
  else
    return 404
  end
end

function Login(Email,Password)
  local Res=Users.index.Login:select({Email,CryptoPassword(Password)})
  local Session=MkSession()
  if #Res==1 and Res[1][6] and pcall(function()
      Users.index.Login:update({Email,CryptoPassword(Password)},{{'=',8,Session}})
    end) then
    return 200,Session
  else
    return 404
  end
end

function LoginOAuth(key,ServiceName,ServiceID)
  if key==Cfg.InternalKey then
    local Res=UsersOAuth:get{ServiceName,ServiceID}
    if Res then
      Res=Users:get(Res[1])
      local Session=MkSession()
      if Res and Res[6] and pcall(function()
          Users:update(Res[1],{{'=',8,Session}})
        end)then
        return 200,Session
      else
        return 404
      end
    else
      return 404
    end
  else
    return 404
  end
end

function MkMailingList(key)
  if key==Cfg.InternalKey then
    local Data={}
    for _,i in Users.index.Mailing:pairs(true) do
      Data[#Data+1]=i[7]
    end
    log.error(Data)
    return 200,Data
  else
    return 200
  end
end

function ResetPassword(Email)
  local Password
  if Users.index.Email:get(Email) then
    if pcall(function()
        Password=GenPassword()
        Users.index.Email:update(Email,{{'=',4,Password}})
      end)then
      local link=[[https://languagerobbers.ru/VerifyEmail?Code=]]..Password
      local r=http_client:get([[https://languagerobbers.ru/SendMail?Key=]]..Cfg.InternalKey.."&Email="..DoPercentEncoding(Email).."&Subject="..DoPercentEncoding(
        "Подтверждение регитсрации на Language Robbers").."&Body="..
        DoPercentEncoding("Уважемый "..UserName..
        '<p>Спасибо за регистрацию на languagerobbers.ru!<p>Для подтверждения вашего email адреса перейдите по следующей ссылке:'..
        '<p><a href="'..link..'">'..link..'</a>'))
      log.error(r.status)
      log.error(r.body)
      log.error(r.reason)
      return r.status
    else
      return 500
    end
  else
    return 404
  end
end

function GetServerDate()
  return 200,math.floor(tonumber(clock.time64())/1000000000/60/60/24)
end

function GetServerTime()
  return 200,tonumber(clock.time64())
end




--Decks
local MaxCardsInDeck=50

function GetDeckList(Session)
  local Res=Users.index.Session:get(Session)
  if #Res==1 and Res[6] then
    Result={}
    for _,i in Decks.index.User:pairs(Res[1]) do
      Result[i[3]]=i
    end
    return 200,Result
  else
    return 404
  end
end

function GetDeck(Session,DeckID)
  local Res=Users.index.Session:get(Session)
  if #Res==1 and Res[6] then
    local Res2=Decks:get(DeckID)
    if Res2 and Res[1]==Res2[1] then
      return 200,DeckCards:select(DeckID)
    end
    return 403
  else
    return 404
  end
end

function NewDeck(Session,Name,Class,Type)
  local Res=Users.index.Session:get(Session)
  if #Res==1 and Res[6] then
    local Result=Decks:insert{Res[1],nil,Name,Class,Type}
    return 200,Result[2]
  else
    return 404
  end
end

function DelDeck(Session,DeckID)
  local Res=Users.index.Session:get(Session)
  if #Res==1 and Res[6] then
    local Res2=Decks:get(DeckID)
    if Res2 and Res[1]==Res2[1] then
      Decks:delete{DeckID}
      for _,i in pairs(DeckCards.index.ID:select(DeckID)) do
        DeckCards:delete(i)
      end
      return 200
    end
    return 403
  else
    return 404
  end
end

--CardsInDecks
function AddCardToDeck(Session,DeckID,CardSet,CardName)
  local Res=Users.index.Session:get(Session)
  if #Res==1 and Res[6] then
    local Res2=Decks:get(DeckID)
    if Res2 and Res[1]==Res2[1] then
      if DeckCards.Decks.ID:count(DeckID)<MaxCardsInDeck then
        for _,i in pairs(DeckCards.index.ID:select(DeckID)) do
          DeckCards:delete(i)
        end
      end
      return 409
    end
    return 403
  else
    return 404
  end
end
end
  --[[Decks=box.schema.space.create('Decks',{engine="vinyl",format={
    {name='UserID',type='unsigned'},
    {name='ID',type='unsigned'},
    {name='Name',type='string'},
    {name='Class',type='unsigned'},
    {name='Type',type='unsigned'}
  }})
  box.schema.sequence.create('DecksSeq')
  Decks:create_index('primary',{unique=true,parts={{1,"unsigned"},{3,"string"}}})
  Decks:create_index('User',{unique=false,parts={{1,"unsigned"}}})
  Decks:create_index('ID',{unique=true,parts={{2,"unsigned"}},sequence='DecksSeq'})

  DeckCards=box.schema.space.create('DeckCards',{engine="vinyl",format={
    {name='DeckID',type='unsigned'},
    {name='CardSet',type='string'},
    {name='CardName',type='string'}
  }})
  DeckCards:create_index('primary',{unique=true,parts={{1,"unsigned"},{2,"string"},{3,"string"}}})
  DeckCards:create_index('ID',{unique=false,parts={{1,"unsigned"}}})]]
